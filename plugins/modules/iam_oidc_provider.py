#!/usr/bin/python
# Copyright: Taylor Kimball
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
    type: dict
  thumbprint_list:
    description:
      - The certificate thumbprints to register with the OIDC provider.
      - This is required when O(state=present).
    elements: str
    type: list
  url:
    description:
      - The OIDC provider URL.
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

from ansible.module_utils.common.dict_transformations import recursive_diff
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


def normalize_provider_url(url):
    if url is None:
        return None
    normalized = url.rstrip("/")
    if normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    return normalized


def list_provider_arns(client, module):
    try:
        return [
            provider["Arn"]
            for provider in client.list_open_id_connect_providers(
                aws_retry=True,
            ).get("OpenIDConnectProviderList", [])
            if provider.get("Arn")
        ]
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS IAM OIDC providers")


def get_provider_by_arn(client, module, arn):
    try:
        provider = client.get_open_id_connect_provider(
            OpenIDConnectProviderArn=arn,
            aws_retry=True,
        )
    except is_boto3_error_code("NoSuchEntity"):
        return None
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS IAM OIDC provider {arn}")

    provider["OpenIDConnectProviderArn"] = arn
    return provider


def get_provider_by_url(client, module, url):
    desired_url = normalize_provider_url(url)
    for arn in list_provider_arns(client, module):
        provider = get_provider_by_arn(client, module, arn)
        if provider and normalize_provider_url(provider.get("Url")) == desired_url:
            return provider
    return None


def comparable_provider(provider):
    if provider is None:
        return None
    normalized = boto3_resource_to_ansible_dict(provider)
    return {
        "client_id_list": sorted(normalized.get("client_id_list") or []),
        "thumbprint_list": sorted(normalized.get("thumbprint_list") or []),
        "url": normalize_provider_url(normalized.get("url")),
    }


def desired_comparable_provider(module):
    return {
        "client_id_list": sorted(module.params["client_id_list"] or []),
        "thumbprint_list": sorted(module.params["thumbprint_list"] or []),
        "url": normalize_provider_url(module.params["url"]),
    }


def apply_client_id_changes(client, module, arn, current, desired):
    current_client_ids = set((current or {}).get("ClientIDList") or [])
    desired_client_ids = set(desired["client_id_list"])

    for client_id in sorted(current_client_ids - desired_client_ids):
        try:
            client.remove_client_id_from_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                ClientID=client_id,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to remove client ID from AWS IAM OIDC provider "
                    f"{module.params['url']}"
                ),
            )

    for client_id in sorted(desired_client_ids - current_client_ids):
        try:
            client.add_client_id_to_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                ClientID=client_id,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to add client ID to AWS IAM OIDC provider "
                    f"{module.params['url']}"
                ),
            )


def apply_thumbprint_changes(client, module, arn, desired):
    try:
        client.update_open_id_connect_provider_thumbprint(
            OpenIDConnectProviderArn=arn,
            ThumbprintList=desired["thumbprint_list"],
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to update thumbprints for AWS IAM OIDC provider "
                f"{module.params['url']}"
            ),
        )


def apply_tag_changes(client, module, arn, tags_to_set, tag_keys_to_unset):
    if tag_keys_to_unset:
        try:
            client.untag_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from AWS IAM OIDC provider {module.params['url']}",
            )

    if tags_to_set:
        try:
            client.tag_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag AWS IAM OIDC provider {module.params['url']}",
            )


def provider_with_updated_tags(provider, tags_to_set, tag_keys_to_unset):
    provider = dict(provider)
    tags = boto3_tag_list_to_ansible_dict((provider or {}).get("Tags", []))
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)
    tags.update(tags_to_set)
    provider["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return provider


def check_mode_provider(module, current=None):
    provider = dict(current or {})
    provider["Url"] = module.params["url"]
    provider["ClientIDList"] = module.params["client_id_list"]
    provider["ThumbprintList"] = module.params["thumbprint_list"]

    if module.params["tags"] is not None:
        current_tags = boto3_tag_list_to_ansible_dict(provider.get("Tags", []))
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current_tags,
            module.params["tags"],
            purge_tags=module.params["purge_tags"],
        )
        for key in tag_keys_to_unset:
            current_tags.pop(key, None)
        current_tags.update(tags_to_set)
        provider["Tags"] = ansible_dict_to_boto3_tag_list(current_tags)

    return provider


def ensure_absent(client, module):
    current = get_provider_by_url(client, module, module.params["url"])
    changed = current is not None
    arn = (current or {}).get("OpenIDConnectProviderArn")

    if changed and not module.check_mode:
        try:
            client.delete_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to delete AWS IAM OIDC provider {module.params['url']}"
            )

    result = {
        "changed": changed,
        "state": "absent",
        "url": module.params["url"],
    }
    if arn:
        result["open_id_connect_provider_arn"] = arn
    module.exit_json(**result)


def ensure_present(client, module):
    current = get_provider_by_url(client, module, module.params["url"])
    desired = desired_comparable_provider(module)
    current_comparable = comparable_provider(current)
    tags_to_set, tag_keys_to_unset = ({}, [])
    if module.params["tags"] is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
            module.params["tags"],
            purge_tags=module.params["purge_tags"],
        )
    resource_changed = recursive_diff((current_comparable) or {}, desired) is not None
    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if current is None:
            try:
                request = {
                    "Url": module.params["url"],
                    "ClientIDList": module.params["client_id_list"],
                    "ThumbprintList": module.params["thumbprint_list"],
                }
                if module.params["tags"] is not None:
                    request["Tags"] = ansible_dict_to_boto3_tag_list(
                        module.params["tags"]
                    )
                arn = client.create_open_id_connect_provider(
                    **request,
                    aws_retry=True,
                ).get("OpenIDConnectProviderArn")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS IAM OIDC provider {module.params['url']}",
                )
        else:
            arn = current["OpenIDConnectProviderArn"]
            provider_changed = False
            if current_comparable["client_id_list"] != desired["client_id_list"]:
                apply_client_id_changes(client, module, arn, current, desired)
                provider_changed = True
            if current_comparable["thumbprint_list"] != desired["thumbprint_list"]:
                apply_thumbprint_changes(client, module, arn, desired)
                provider_changed = True
            apply_tag_changes(
                client,
                module,
                arn,
                tags_to_set,
                tag_keys_to_unset,
            )
            if provider_changed:
                current = get_provider_by_arn(client, module, arn) if arn else None
            else:
                current = provider_with_updated_tags(
                    current, tags_to_set, tag_keys_to_unset
                )
        if current is None:
            current = get_provider_by_arn(client, module, arn) if arn else None
    elif changed and module.check_mode:
        current = check_mode_provider(module, current)

    result = {
        "changed": changed,
        "open_id_connect_provider": boto3_resource_to_ansible_dict(current or {}),
        "state": "present",
        "url": module.params["url"],
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
    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
