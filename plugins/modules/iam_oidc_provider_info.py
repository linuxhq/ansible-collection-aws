#!/usr/bin/python
# Copyright: Taylor Kimball
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
    type: str
  url:
    description:
      - Optional IAM OIDC provider URL used to limit the result set.
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

    if module.params["arn"]:
        try:
            provider = client.get_open_id_connect_provider(
                OpenIDConnectProviderArn=module.params["arn"],
                aws_retry=True,
            )
        except is_boto3_error_code("NoSuchEntity"):
            provider = None
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS IAM OIDC provider {module.params['arn']}",
            )

        if provider:
            provider["OpenIDConnectProviderArn"] = module.params["arn"]

        providers = [provider] if provider else []
    elif module.params["url"]:
        providers = []
        desired_url = normalize_provider_url(module.params["url"])

        for arn in list_provider_arns(client, module):
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
        open_id_connect_providers=boto3_resource_list_to_ansible_dict(providers),
    )


if __name__ == "__main__":
    main()
