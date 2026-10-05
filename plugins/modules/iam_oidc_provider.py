#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_oidc_provider
short_description: Manage AWS IAM OIDC providers
version_added: "1.9.0"
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
      - This must contain at most 100 unique entries.
      - When omitted while creating a provider, AWS registers no client IDs.
      - When omitted while updating a provider, the existing client IDs are left unchanged.
      - An empty list removes all client IDs.
    elements: str
    type: list
  state:
    description:
      - Whether the IAM OIDC provider should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  thumbprint_list:
    description:
      - The certificate thumbprints to register with the OIDC provider.
      - Each thumbprint must be exactly 40 hexadecimal characters.
      - This must contain at most 5 unique entries.
      - When omitted while creating a provider, IAM retrieves the thumbprint of the
        provider's top intermediate certificate authority.
      - When omitted while updating a provider, the existing thumbprints are left unchanged.
    elements: str
    type: list
  url:
    description:
      - The OIDC provider URL.
      - The URL must begin with C(https://) when O(state=present).
      - The URL must be at most 255 characters and identify a host.
      - Matching against an existing provider ignores the C(https://) prefix
        and any trailing slash, and compares the host case-insensitively.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: The module predicts OIDC provider changes without applying them.
    support: full
  diff_mode:
    description: The module does not return diff data.
    support: none
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

- name: Ensure an IAM OIDC provider is present with an IAM-retrieved thumbprint
  linuxhq.aws.iam_oidc_provider:
    url: https://token.actions.githubusercontent.com
    client_id_list:
      - sts.amazonaws.com

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
  contains:
    client_id_list:
      description: The client IDs registered with the provider.
      returned: >-
        when the provider exists, or in check mode when a provider would be created and
        O(client_id_list) is specified
      type: list
      elements: str
    create_date:
      description: The time the provider was created.
      returned: when returned by AWS
      type: str
    open_id_connect_provider_arn:
      description: The provider ARN.
      returned: when the provider exists; not returned in check mode when a provider would be created
      type: str
    tags:
      description: Tags applied to the provider.
      returned: when available
      type: dict
    thumbprint_list:
      description: The certificate thumbprints registered with the provider.
      returned: >-
        when the provider exists, or in check mode when a provider would be created and
        O(thumbprint_list) is specified
      type: list
      elements: str
    url:
      description: The normalized provider URL.
      returned: always
      type: str
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
    validate_provider_summaries,
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

    providers = validate_provider_summaries(
        module,
        query_list(
            module,
            client,
            "list_open_id_connect_providers",
            "OpenIDConnectProviderList",
            "Unable to list AWS IAM OIDC providers",
        ),
    )

    for provider_summary in providers:
        arn = provider_summary["Arn"]

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
    desired = {"url": normalize_provider_url(url)}
    if module.params["client_id_list"] is not None:
        desired["client_id_list"] = sorted(set(module.params["client_id_list"]))

    if module.params["thumbprint_list"] is not None:
        desired["thumbprint_list"] = sorted({thumbprint.lower() for thumbprint in module.params["thumbprint_list"]})

    current_comparable = None
    if current is not None:
        current_comparable = {
            "client_id_list": sorted(set(current.get("ClientIDList") or [])),
            "thumbprint_list": sorted({thumbprint.lower() for thumbprint in current.get("ThumbprintList") or []}),
            "url": normalize_provider_url(current.get("Url")),
        }
        current_comparable = {key: value for key, value in current_comparable.items() if key in desired}

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
            request = {"Url": f"https://{desired['url']}"}
            if "client_id_list" in desired:
                request["ClientIDList"] = desired["client_id_list"]

            if "thumbprint_list" in desired:
                request["ThumbprintList"] = desired["thumbprint_list"]

            if tags:
                request["Tags"] = ansible_dict_to_boto3_tag_list(tags)

            # The provider is read back after creation, so that call is checked before creating anything.
            require_client_methods(
                module,
                client,
                "IAM",
                {
                    "create_open_id_connect_provider": tuple(request),
                    "get_open_id_connect_provider": ("OpenIDConnectProviderArn",),
                },
            )
            try:
                response = client.create_open_id_connect_provider(
                    **request,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS IAM OIDC provider {url}",
                )

            if (
                not isinstance(response, dict)
                or not isinstance(response.get("OpenIDConnectProviderArn"), str)
                or not response["OpenIDConnectProviderArn"]
            ):
                module.fail_json(
                    changed=True,
                    msg=f"Unable to create AWS IAM OIDC provider {url}: AWS returned an invalid response",
                )

            arn = response["OpenIDConnectProviderArn"]

            current = get_provider_by_arn(client, module, arn, changed=True) or dict(
                request, OpenIDConnectProviderArn=arn, Url=desired["url"]
            )
        else:
            arn = current["OpenIDConnectProviderArn"]
            provider_changed = False
            client_ids_changed = (
                "client_id_list" in desired and current_comparable["client_id_list"] != desired["client_id_list"]
            )
            thumbprints_changed = (
                "thumbprint_list" in desired and current_comparable["thumbprint_list"] != desired["thumbprint_list"]
            )
            current_client_ids = set(current.get("ClientIDList") or [])
            removed_client_ids, added_client_ids = [], []
            if client_ids_changed:
                desired_client_ids = set(desired["client_id_list"])
                removed_client_ids = sorted(current_client_ids - desired_client_ids)
                added_client_ids = sorted(desired_client_ids - current_client_ids)

            # Every write is checked before the first one, so an older botocore fails without modifying anything.
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

            if thumbprints_changed:
                methods["update_open_id_connect_provider_thumbprint"] = (
                    "OpenIDConnectProviderArn",
                    "ThumbprintList",
                )

            if tag_keys_to_unset:
                methods["untag_open_id_connect_provider"] = (
                    "OpenIDConnectProviderArn",
                    "TagKeys",
                )

            if tags_to_set:
                methods["tag_open_id_connect_provider"] = (
                    "OpenIDConnectProviderArn",
                    "Tags",
                )

            require_client_methods(module, client, "IAM", methods)

            if client_ids_changed:
                # Free only the capacity needed before adding replacement audiences.
                remove_first = max(0, len(current_client_ids) + len(added_client_ids) - 100)
                operations = (
                    [("remove", client_id) for client_id in removed_client_ids[:remove_first]]
                    + [("add", client_id) for client_id in added_client_ids]
                    + [("remove", client_id) for client_id in removed_client_ids[remove_first:]]
                )
                for action, client_id in operations:
                    method = (
                        client.add_client_id_to_open_id_connect_provider
                        if action == "add"
                        else client.remove_client_id_from_open_id_connect_provider
                    )
                    try:
                        method(
                            OpenIDConnectProviderArn=arn,
                            ClientID=client_id,
                            aws_retry=True,
                        )
                    except (BotoCoreError, ClientError) as e:
                        module.fail_json_aws(
                            e,
                            changed=provider_changed,
                            msg=f"Unable to {action} client ID for AWS IAM OIDC provider {url}",
                        )

                    provider_changed = True

                provider_changed = True

            if thumbprints_changed:
                try:
                    client.update_open_id_connect_provider_thumbprint(
                        OpenIDConnectProviderArn=arn,
                        ThumbprintList=desired["thumbprint_list"],
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        changed=provider_changed,
                        msg=f"Unable to update thumbprints for AWS IAM OIDC provider {url}",
                    )

                provider_changed = True

            if tag_keys_to_unset:
                try:
                    client.untag_open_id_connect_provider(
                        OpenIDConnectProviderArn=arn,
                        TagKeys=tag_keys_to_unset,
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        changed=provider_changed,
                        msg=f"Unable to remove tags from AWS IAM OIDC provider {url}",
                    )

            if tags_to_set:
                try:
                    client.tag_open_id_connect_provider(
                        OpenIDConnectProviderArn=arn,
                        Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        changed=provider_changed or bool(tag_keys_to_unset),
                        msg=f"Unable to tag AWS IAM OIDC provider {url}",
                    )

            if provider_changed:
                current = dict(current)
                if "client_id_list" in desired:
                    current["ClientIDList"] = desired["client_id_list"]

                if "thumbprint_list" in desired:
                    current["ThumbprintList"] = desired["thumbprint_list"]

            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode:
        current = dict(current or {})
        current["Url"] = desired["url"]
        if "client_id_list" in desired:
            current["ClientIDList"] = desired["client_id_list"]

        if "thumbprint_list" in desired:
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
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
        "thumbprint_list": {"elements": "str", "type": "list"},
        "url": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    state = module.params["state"]

    if state == "present":
        if not module.params["url"].lower().startswith("https://"):
            module.fail_json(msg="url must begin with https://")

        normalized_url = normalize_provider_url(module.params["url"])
        if not normalized_url or not normalized_url.partition("/")[0]:
            module.fail_json(msg="url must identify an OIDC provider host")

        if len(module.params["url"]) > 255:
            module.fail_json(msg="url must contain at most 255 characters")

        if len(set(module.params["client_id_list"] or [])) > 100:
            module.fail_json(msg="client_id_list must contain at most 100 unique entries")

        if len({item.lower() for item in module.params["thumbprint_list"] or []}) > 5:
            module.fail_json(msg="thumbprint_list must contain at most 5 unique entries")

        for client_id in module.params["client_id_list"] or []:
            if not 1 <= len(client_id) <= 255:
                module.fail_json(msg=f"client_id_list entries must be 1 to 255 characters: {client_id}")

        for thumbprint in module.params["thumbprint_list"] or []:
            if not re.fullmatch(r"[0-9a-fA-F]{40}", thumbprint):
                module.fail_json(msg=f"thumbprint_list entries must be exactly 40 hexadecimal characters: {thumbprint}")

    require_valid_tags(module, module.params["tags"] if state == "present" else None, 50)
    client = module.client(
        "iam",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["ConcurrentModification"]),
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
