#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_oidc_provider
short_description: Manage aws iam oidc providers
description:
  - Manages AWS IAM OpenID Connect (OIDC) identity providers.
  - Supports creating and deleting providers, and updating client IDs, thumbprints, and tags.
author:
  - Taylor Kimball (@tkimball83)
options:
  client_id_list:
    description:
      - The client IDs, also known as audiences, to register with the OIDC provider.
      - Each client ID must be 1 to 255 characters.
      - This must contain at least 1 and at most 100 unique entries.
      - This is required when O(state=present).
    elements: str
    type: list
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  state:
    description:
      - Whether the IAM OIDC provider should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the OIDC provider.
      - This must contain at most 50 entries; keys must contain 1 to 128 characters and values at most 256 characters.
    type: dict
  thumbprint_list:
    description:
      - The certificate thumbprints to register with the OIDC provider.
      - Each thumbprint must be exactly 40 hexadecimal characters.
      - This must contain at least 1 and at most 5 unique entries.
      - This is required when O(state=present).
    elements: str
    type: list
  url:
    description:
      - The OIDC provider URL.
      - The URL must begin with C(https://) when O(state=present).
      - Matching against an existing provider ignores the C(https://) prefix
        and any trailing slash, and compares the host case-insensitively.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure an IAM OIDC provider is present
  linuxhq.aws.iam_oidc_provider:
    url: https://token.actions.githubusercontent.com
    client_id_list:
      - sts.amazonaws.com
    thumbprint_list:
      - 6938fd4d98bab03faadb97b34396831e3780aea1
    tags:
      Name: github-actions

- name: Ensure an IAM OIDC provider is absent
  linuxhq.aws.iam_oidc_provider:
    url: https://token.actions.githubusercontent.com
    state: absent
"""

RETURN = r"""
open_id_connect_provider:
  description:
    - The current IAM OIDC provider after module execution.
  returned: when state is present
  type: dict
open_id_connect_provider_arn:
  description:
    - The IAM OIDC provider ARN.
  returned: when an OIDC provider exists or existed before deletion
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
url:
  description:
    - The requested OIDC provider URL.
  returned: always
  type: str
"""

import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.iam_oidc import (
    get_provider_by_arn,
    normalize_provider_url,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    require_valid_tags,
)


def get_provider_by_url(client, module):
    desired_url = normalize_provider_url(module.params["url"])

    providers = query_list(
        module,
        client,
        "list_open_id_connect_providers",
        "OpenIDConnectProviderList",
        "Unable to list AWS IAM OIDC providers",
    )

    for provider_summary in providers:
        arn = provider_summary.get("Arn")

        if not arn:
            continue

        arn_url = arn.partition(":oidc-provider/")[2]
        if normalize_provider_url(arn_url) != desired_url:
            continue

        require_client_methods(
            module,
            client,
            "IAM",
            {"get_open_id_connect_provider": ("OpenIDConnectProviderArn",)},
        )
        provider = get_provider_by_arn(client, module, arn)

        if provider and normalize_provider_url(provider.get("Url")) == desired_url:
            return provider
    return None


def ensure_absent(client, module):
    url = module.params["url"]
    current = get_provider_by_url(client, module)
    changed = current is not None
    arn = (current or {}).get("OpenIDConnectProviderArn")

    if changed and not module.check_mode:
        require_client_methods(
            module,
            client,
            "IAM",
            {"delete_open_id_connect_provider": ("OpenIDConnectProviderArn",)},
        )
        try:
            client.delete_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                aws_retry=True,
            )
        except is_boto3_error_code("NoSuchEntity"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to delete AWS IAM OIDC provider {url}")

    result = {
        "changed": changed,
        "state": "absent",
        "url": url,
    }
    if arn:
        result["open_id_connect_provider_arn"] = arn
    module.exit_json(**result)


def ensure_present(client, module):
    tags = module.params["tags"]
    url = module.params["url"]
    current = get_provider_by_url(client, module)
    desired = {
        "client_id_list": sorted(set(module.params["client_id_list"] or [])),
        "thumbprint_list": sorted({thumbprint.lower() for thumbprint in module.params["thumbprint_list"] or []}),
        "url": normalize_provider_url(url),
    }
    current_comparable = None
    if current is not None:
        current_comparable = {
            "client_id_list": sorted(set(current.get("ClientIDList") or [])),
            "thumbprint_list": sorted({thumbprint.lower() for thumbprint in current.get("ThumbprintList") or []}),
            "url": normalize_provider_url(current.get("Url")),
        }

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
            tags,
            purge_tags=module.params["purge_tags"],
        )
    resource_changed = (current_comparable or {}) != desired
    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if current is None:
            request = {
                "Url": f"https://{desired['url']}",
                "ClientIDList": desired["client_id_list"],
                "ThumbprintList": desired["thumbprint_list"],
            }
            if tags:
                request["Tags"] = ansible_dict_to_boto3_tag_list(tags)

            require_client_methods(
                module,
                client,
                "IAM",
                {"create_open_id_connect_provider": tuple(request)},
            )
            try:
                arn = client.create_open_id_connect_provider(
                    **request,
                    aws_retry=True,
                ).get("OpenIDConnectProviderArn")
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS IAM OIDC provider {url}",
                )

            if not arn:
                module.fail_json(msg=f"AWS IAM did not return an ARN for OIDC provider {url}")

            require_client_methods(
                module,
                client,
                "IAM",
                {"get_open_id_connect_provider": ("OpenIDConnectProviderArn",)},
            )
            current = get_provider_by_arn(client, module, arn) or dict(
                request, OpenIDConnectProviderArn=arn, Url=desired["url"]
            )
        else:
            arn = current["OpenIDConnectProviderArn"]
            provider_changed = False
            if current_comparable["client_id_list"] != desired["client_id_list"]:
                current_client_ids = set(current.get("ClientIDList") or [])
                desired_client_ids = set(desired["client_id_list"])

                removed_client_ids = sorted(current_client_ids - desired_client_ids)
                added_client_ids = sorted(desired_client_ids - current_client_ids)
                methods = {}
                if removed_client_ids:
                    methods["remove_client_id_from_open_id_connect_provider"] = (
                        "ClientID",
                        "OpenIDConnectProviderArn",
                    )
                if added_client_ids:
                    methods["add_client_id_to_open_id_connect_provider"] = (
                        "ClientID",
                        "OpenIDConnectProviderArn",
                    )
                require_client_methods(module, client, "IAM", methods)

                for client_id in removed_client_ids:
                    try:
                        client.remove_client_id_from_open_id_connect_provider(
                            OpenIDConnectProviderArn=arn,
                            ClientID=client_id,
                            aws_retry=True,
                        )
                    except (BotoCoreError, ClientError) as e:
                        module.fail_json_aws(
                            e,
                            msg=("Unable to remove client ID from AWS IAM OIDC " f"provider {url}"),
                        )

                for client_id in added_client_ids:
                    try:
                        client.add_client_id_to_open_id_connect_provider(
                            OpenIDConnectProviderArn=arn,
                            ClientID=client_id,
                            aws_retry=True,
                        )
                    except (BotoCoreError, ClientError) as e:
                        module.fail_json_aws(
                            e,
                            msg=("Unable to add client ID to AWS IAM OIDC " f"provider {url}"),
                        )

                provider_changed = True

            if current_comparable["thumbprint_list"] != desired["thumbprint_list"]:
                require_client_methods(
                    module,
                    client,
                    "IAM",
                    {
                        "update_open_id_connect_provider_thumbprint": (
                            "OpenIDConnectProviderArn",
                            "ThumbprintList",
                        )
                    },
                )
                try:
                    client.update_open_id_connect_provider_thumbprint(
                        OpenIDConnectProviderArn=arn,
                        ThumbprintList=desired["thumbprint_list"],
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=("Unable to update thumbprints for AWS IAM OIDC " f"provider {url}"),
                    )

                provider_changed = True

            if tag_keys_to_unset:
                require_client_methods(
                    module,
                    client,
                    "IAM",
                    {
                        "untag_open_id_connect_provider": (
                            "OpenIDConnectProviderArn",
                            "TagKeys",
                        )
                    },
                )
                try:
                    client.untag_open_id_connect_provider(
                        OpenIDConnectProviderArn=arn,
                        TagKeys=tag_keys_to_unset,
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=f"Unable to remove tags from AWS IAM OIDC provider {url}",
                    )

            if tags_to_set:
                require_client_methods(
                    module,
                    client,
                    "IAM",
                    {
                        "tag_open_id_connect_provider": (
                            "OpenIDConnectProviderArn",
                            "Tags",
                        )
                    },
                )
                try:
                    client.tag_open_id_connect_provider(
                        OpenIDConnectProviderArn=arn,
                        Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(e, msg=f"Unable to tag AWS IAM OIDC provider {url}")

            if provider_changed:
                current = dict(
                    current,
                    ClientIDList=desired["client_id_list"],
                    ThumbprintList=desired["thumbprint_list"],
                )
            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode:
        current = dict(current or {})
        current["Url"] = desired["url"]
        current["ClientIDList"] = desired["client_id_list"]
        current["ThumbprintList"] = desired["thumbprint_list"]

        if tags is not None:
            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

    result = {
        "changed": changed,
        "open_id_connect_provider": boto3_resource_to_ansible_dict(
            current or {}, transform_tags=True, force_tags=False
        ),
        "state": "present",
        "url": url,
    }
    arn = (current or {}).get("OpenIDConnectProviderArn")

    if arn:
        result["open_id_connect_provider_arn"] = arn
    module.exit_json(**result)


def main():
    argument_spec = {
        "client_id_list": {"elements": "str", "type": "list"},
        "purge_tags": {"default": True, "type": "bool"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"type": "dict"},
        "thumbprint_list": {"elements": "str", "type": "list"},
        "url": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["client_id_list", "thumbprint_list"])],
        supports_check_mode=True,
    )
    state = module.params["state"]

    if state == "present":
        if not module.params["url"].lower().startswith("https://"):
            module.fail_json(msg="url must begin with https://")
        if len(set(module.params["client_id_list"])) > 100:
            module.fail_json(msg="client_id_list must contain at most 100 unique entries")
        if len({item.lower() for item in module.params["thumbprint_list"]}) > 5:
            module.fail_json(msg="thumbprint_list must contain at most 5 unique entries")
        if not module.params["client_id_list"]:
            module.fail_json(msg="client_id_list must contain at least 1 entry")
        if not module.params["thumbprint_list"]:
            module.fail_json(msg="thumbprint_list must contain at least 1 entry")

        for client_id in module.params["client_id_list"]:
            if not 1 <= len(client_id) <= 255:
                module.fail_json(msg=f"client_id_list entries must be 1 to 255 characters: {client_id}")

        for thumbprint in module.params["thumbprint_list"]:
            if not re.fullmatch(r"[0-9a-fA-F]{40}", thumbprint):
                module.fail_json(
                    msg=("thumbprint_list entries must be exactly 40 hexadecimal " f"characters: {thumbprint}")
                )

    require_valid_tags(module, module.params["tags"] if state == "present" else None, 50)
    client = module.client(
        "iam",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["ConcurrentModificationException"]),
    )
    require_client_methods(
        module,
        client,
        "IAM",
        {"list_open_id_connect_providers": ()},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
