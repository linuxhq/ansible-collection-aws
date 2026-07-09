#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_oidc_provider_info
short_description: Gather information about aws iam oidc providers
description:
  - Gathers information about AWS IAM OpenID Connect (OIDC) identity providers.
author:
  - Taylor Kimball (@tkimball83)
options:
  arn:
    description:
      - Optional IAM OIDC provider ARN used to limit the result set.
      - Mutually exclusive with O(url).
    type: str
  url:
    description:
      - Optional IAM OIDC provider URL used to limit the result set.
      - Matching ignores the C(https://) prefix and any trailing slash.
      - Mutually exclusive with O(arn).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about IAM OIDC providers
  linuxhq.aws.iam_oidc_provider_info:

- name: Gather information about one IAM OIDC provider by URL
  linuxhq.aws.iam_oidc_provider_info:
    url: https://token.actions.githubusercontent.com

- name: Gather information about one IAM OIDC provider by ARN
  linuxhq.aws.iam_oidc_provider_info:
    arn: arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com
"""

RETURN = r"""
open_id_connect_providers:
  description:
    - The IAM OIDC providers.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
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
        providers = client.list_open_id_connect_providers(
            aws_retry=True,
        ).get("OpenIDConnectProviderList", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS IAM OIDC providers")

    arns = []
    for provider in providers:
        arn = provider.get("Arn")

        if arn:
            arns.append(arn)
    return arns


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


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "arn": {"type": "str"},
            "url": {"type": "str"},
        },
        mutually_exclusive=[["arn", "url"]],
        supports_check_mode=True,
    )
    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())

    arn = module.params["arn"]
    url = module.params["url"]
    method_names = {"get_open_id_connect_provider"}
    if not arn:
        method_names.add("list_open_id_connect_providers")

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
        "get_open_id_connect_provider": {"OpenIDConnectProviderArn"},
    }
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

    if arn:
        provider = get_provider_by_arn(client, module, arn)
        providers = [provider] if provider else []
    elif url:
        providers = []
        desired_url = normalize_provider_url(url)

        for arn in list_provider_arns(client, module):
            if not arn.endswith(f":oidc-provider/{desired_url}"):
                continue

            provider = get_provider_by_arn(client, module, arn)

            if provider and normalize_provider_url(provider.get("Url")) == desired_url:
                providers.append(provider)
                break
    else:
        providers = []
        for arn in list_provider_arns(client, module):
            provider = get_provider_by_arn(client, module, arn)

            if provider:
                providers.append(provider)

    module.exit_json(
        changed=False,
        open_id_connect_providers=boto3_resource_list_to_ansible_dict(
            providers, transform_tags=True, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
