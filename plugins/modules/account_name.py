#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: account_name
short_description: Manage the AWS account name
version_added: "2.5.0"
description:
  - Manages the AWS account name using AWS Account Management.
  - Requires a botocore version exposing C(get_account_information).
  - Updates require a botocore version exposing C(put_account_name).
  - Requires C(account:GetAccountInformation) and C(account:PutAccountName) IAM permissions.
author:
  - Taylor Kimball (@tkimball83)
options:
  account_id:
    description:
      - The 12-digit ID of a member account in the same organization.
      - Omit to use the account of the calling identity, including a management account.
      - Cross-account access requires organization management or delegated administrator credentials,
        all organization features, and trusted access for Account Management.
    type: str
  name:
    description:
      - The desired account name, containing 1 to 50 printable ASCII characters except angle brackets.
      - Account names cannot be deleted.
    type: str
    required: true
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Predicts a name change without updating the account.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Manage the AWS account name
  linuxhq.aws.account_name:
    name: Production

- name: Manage the AWS account name for a member account
  linuxhq.aws.account_name:
    account_id: "123456789012"
    name: Production
"""

RETURN = r"""
account:
  description: AWS account information.
  returned: always
  type: dict
  contains:
    account_name:
      description: The current account name, or the predicted name in check mode.
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

import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.account import account_parameters, get_account
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods


def ensure_present(module, client, params):
    account = get_account(module, client, params)
    name = module.params["name"]
    changed = account["account_name"] != name
    if changed:
        if module.check_mode:
            account["account_name"] = name
        else:
            require_client_methods(module, client, "Account", {"put_account_name": ("AccountId", "AccountName")})
            try:
                client.put_account_name(AccountName=name, **params, aws_retry=True)
            except (BotoCoreError, ClientError) as e:
                target = params.get("AccountId", "current account")
                module.fail_json_aws(e, msg=f"Unable to update account name for {target}")

            account = get_account(module, client, params)

    module.exit_json(changed=changed, account=account)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "account_id": {"type": "str"},
            "name": {"type": "str", "required": True},
        },
        supports_check_mode=True,
    )
    params = account_parameters(module)
    name = module.params["name"]
    if not 1 <= len(name) <= 50 or not re.fullmatch(r"[ -;=?-~]+", name):
        module.fail_json(msg="name must contain 1 to 50 printable ASCII characters except angle brackets")

    client = module.client("account", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(module, client, "Account", {"get_account_information": ("AccountId",)})
    ensure_present(module, client, params)


if __name__ == "__main__":
    main()
