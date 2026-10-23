#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_oidc_provider_info
short_description: Gather information about AWS IAM OIDC providers
version_added: "1.9.0"
description:
  - Gathers information about AWS IAM OpenID Connect (OIDC) identity providers.
author:
  - Taylor Kimball (@tkimball83)
options:
  arn:
    description:
      - Optional IAM OIDC provider ARN used to limit the result set.
      - A provider that does not exist results in an empty list.
      - Mutually exclusive with O(url).
    type: str
  url:
    description:
      - Optional IAM OIDC provider URL used to limit the result set.
      - Matching ignores the C(https://) prefix and any trailing slash, and compares
        the host case-insensitively.
      - Mutually exclusive with O(arn).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module does not modify state.
    support: full
  diff_mode:
    description: This module does not modify state.
    support: none
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
  contains:
    client_id_list:
      description: The client IDs registered with the provider.
      returned: always
      type: list
      elements: str
    create_date:
      description: The time the provider was created.
      returned: when returned by AWS
      type: str
    open_id_connect_provider_arn:
      description: The provider ARN.
      returned: always
      type: str
    tags:
      description: Tags applied to the provider.
      returned: when available
      type: dict
    thumbprint_list:
      description: The certificate thumbprints registered with the provider.
      returned: always
      type: list
      elements: str
    url:
      description: The normalized provider URL.
      returned: always
      type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.iam_oidc import (
    get_provider,
    get_provider_by_url,
    list_provider_summaries,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods


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
    if not arn:
        require_client_methods(
            module,
            client,
            "IAM",
            {"list_open_id_connect_providers": ()},
        )

    if arn:
        provider = get_provider(client, module, arn)
        providers = [provider] if provider else []
    elif url:
        provider = get_provider_by_url(client, module, url)
        providers = [provider] if provider else []
    else:
        providers = []
        for provider_summary in list_provider_summaries(client, module):
            provider = get_provider(client, module, provider_summary["Arn"])

            if provider:
                providers.append(provider)

    module.exit_json(
        changed=False,
        open_id_connect_providers=boto3_resource_list_to_ansible_dict(providers, transform_tags=True, force_tags=False),
    )


if __name__ == "__main__":
    main()
