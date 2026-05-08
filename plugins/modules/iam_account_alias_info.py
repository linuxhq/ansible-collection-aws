#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_account_alias_info
version_added: "1.9.5"
short_description: Gather AWS IAM account alias information
description:
  - Gathers AWS IAM account aliases for the current account.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather IAM account alias information
  linuxhq.aws.iam_account_alias_info:
"""

RETURN = r"""
account_aliases:
  description:
    - The IAM account aliases for the current account.
  returned: always
  type: list
  elements: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry


def main():
    module = AnsibleAWSModule(
        argument_spec={},
        supports_check_mode=True,
    )
    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())

    module.exit_json(
        changed=False,
        account_aliases=paginated_query_with_retries(
            client, "list_account_aliases"
        ).get("AccountAliases", []),
    )


if __name__ == "__main__":
    main()
