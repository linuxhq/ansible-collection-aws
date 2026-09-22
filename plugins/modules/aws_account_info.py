#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: aws_account_info
short_description: Gather AWS account information
version_added: "2.5.0"
description:
  - Gathers AWS account information using AWS Account Management.
  - Requires botocore 1.38.0 or later.
  - Requires the C(account:GetAccountInformation) IAM permission.
author:
  - Taylor Kimball (@tkimball83)
options:
  account_id:
    description:
      - The 12-digit ID of a member account in the same organization.
      - Omit to use the account of the calling identity, including a management account.
      - Cross-account access requires organization management or delegated administrator credentials,
        all organization features, and trusted access for Account Management.
      - Requires botocore 1.38.0 or later.
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
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather AWS account information
  linuxhq.aws.aws_account_info:
    region: us-east-1

- name: Gather AWS account information for a member account
  linuxhq.aws.aws_account_info:
    account_id: "123456789012"
"""

RETURN = r"""
account:
  description: AWS account information.
  returned: always
  type: dict
  contains:
    account_name:
      description: The current account name.
      returned: always
      type: str
    account_id:
      description: The AWS account ID.
      returned: when returned by AWS
      type: str
    account_created_date:
      description: Account creation date and time in ISO 8601 format.
      returned: when returned by AWS
      type: str
    account_state:
      description: The account lifecycle state, PENDING_ACTIVATION, ACTIVE, SUSPENDED, or CLOSED.
      returned: when returned by AWS
      type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.account import account_parameters, get_account
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "account_id": {"type": "str"},
        },
        supports_check_mode=True,
    )
    params = account_parameters(module)
    client = module.client("account", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(module, client, "Account", {"get_account_information": ("AccountId",)})
    module.exit_json(changed=False, account=get_account(module, client, params))


if __name__ == "__main__":
    main()
