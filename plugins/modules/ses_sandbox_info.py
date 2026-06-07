#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox_info
short_description: Gather information about aws simple email service account details
description:
  - Gathers information about AWS Simple Email Service account details.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about SES account details
  linuxhq.aws.ses_sandbox_info:
"""

RETURN = r"""
account:
  description:
    - Information about the AWS Simple Email Service account.
  returned: always
  type: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    try:
        account = client.get_account(aws_retry=True)
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to get AWS Simple Email Service account details"
        )

    module.exit_json(
        changed=False,
        account=boto3_resource_to_ansible_dict(
            account,
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
