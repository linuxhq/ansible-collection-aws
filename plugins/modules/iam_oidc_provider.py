#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - Each thumbprint must be exactly 40 characters.
      - This is required when O(state=present).
    elements: str
    type: list
  url:
    description:
      - The OIDC provider URL.
      - Matching against an existing provider ignores the C(https://) prefix
        and any trailing slash.
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
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


def apply_tag_deltas(provider, tags_to_set, tag_keys_to_unset):
    updated = dict(provider)
    updated_tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        updated_tags.pop(tag_key, None)
    updated_tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(updated_tags)
    return updated


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

    provider.pop("ResponseMetadata", None)
    provider["OpenIDConnectProviderArn"] = arn
    return provider


def get_provider_by_url(client, module):
    desired_url = normalize_provider_url(module.params["url"])

    try:
        providers = client.list_open_id_connect_providers(
            aws_retry=True,
        ).get("OpenIDConnectProviderList", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS IAM OIDC providers")

    for provider_summary in providers:
        arn = provider_summary.get("Arn")

        if not arn:
            continue

        if not arn.endswith(f":oidc-provider/{desired_url}"):
            continue

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
        try:
            client.delete_open_id_connect_provider(
                OpenIDConnectProviderArn=arn,
                aws_retry=True,
            )
        except Exception as e:
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
        "thumbprint_list": sorted(set(module.params["thumbprint_list"] or [])),
        "url": normalize_provider_url(url),
    }
    current_comparable = None
    if current is not None:
        current_comparable = {
            "client_id_list": sorted(set(current.get("ClientIDList") or [])),
            "thumbprint_list": sorted(set(current.get("ThumbprintList") or [])),
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
                "Url": url,
                "ClientIDList": desired["client_id_list"],
                "ThumbprintList": desired["thumbprint_list"],
            }
            if tags is not None:
                request["Tags"] = ansible_dict_to_boto3_tag_list(tags)

            try:
                arn = client.create_open_id_connect_provider(
                    **request,
                    aws_retry=True,
                ).get("OpenIDConnectProviderArn")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS IAM OIDC provider {url}",
                )

            current = get_provider_by_arn(client, module, arn) if arn else None
        else:
            arn = current["OpenIDConnectProviderArn"]
            provider_changed = False
            if current_comparable["client_id_list"] != desired["client_id_list"]:
                current_client_ids = set(current.get("ClientIDList") or [])
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
                                "Unable to remove client ID from AWS IAM OIDC "
                                f"provider {url}"
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
                                "Unable to add client ID to AWS IAM OIDC "
                                f"provider {url}"
                            ),
                        )

                provider_changed = True

            if current_comparable["thumbprint_list"] != desired["thumbprint_list"]:
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
                            "Unable to update thumbprints for AWS IAM OIDC "
                            f"provider {url}"
                        ),
                    )

                provider_changed = True

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
                        msg=f"Unable to remove tags from AWS IAM OIDC provider {url}",
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
                        e, msg=f"Unable to tag AWS IAM OIDC provider {url}"
                    )

            if provider_changed:
                current = get_provider_by_arn(client, module, arn) if arn else None
            else:
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
    tags = module.params["tags"]

    if state == "present":
        for client_id in module.params["client_id_list"]:
            if not 1 <= len(client_id) <= 255:
                module.fail_json(
                    msg=f"client_id_list entries must be 1 to 255 characters: {client_id}"
                )

        for thumbprint in module.params["thumbprint_list"]:
            if len(thumbprint) != 40:
                module.fail_json(
                    msg=f"thumbprint_list entries must be exactly 40 characters: {thumbprint}"
                )

    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())
    method_names = {
        "get_open_id_connect_provider",
        "list_open_id_connect_providers",
    }
    if state == "present":
        method_names.update(
            {
                "add_client_id_to_open_id_connect_provider",
                "create_open_id_connect_provider",
                "remove_client_id_from_open_id_connect_provider",
                "update_open_id_connect_provider_thumbprint",
            }
        )
        if tags is not None:
            method_names.add("tag_open_id_connect_provider")
            if module.params["purge_tags"]:
                method_names.add("untag_open_id_connect_provider")

    if state == "absent":
        method_names.add("delete_open_id_connect_provider")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support IAM {method_name}"
            )

    required_method_parameters = {
        "add_client_id_to_open_id_connect_provider": {
            "ClientID",
            "OpenIDConnectProviderArn",
        },
        "create_open_id_connect_provider": {
            "ClientIDList",
            "ThumbprintList",
            "Url",
        },
        "delete_open_id_connect_provider": {"OpenIDConnectProviderArn"},
        "get_open_id_connect_provider": {"OpenIDConnectProviderArn"},
        "remove_client_id_from_open_id_connect_provider": {
            "ClientID",
            "OpenIDConnectProviderArn",
        },
        "tag_open_id_connect_provider": {"OpenIDConnectProviderArn", "Tags"},
        "untag_open_id_connect_provider": {"OpenIDConnectProviderArn", "TagKeys"},
        "update_open_id_connect_provider_thumbprint": {
            "OpenIDConnectProviderArn",
            "ThumbprintList",
        },
    }
    if state == "present" and tags is not None:
        required_method_parameters["create_open_id_connect_provider"].add("Tags")

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support IAM "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
