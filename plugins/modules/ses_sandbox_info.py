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
from ansible_collections.linuxhq.aws.plugins.module_utils.ses import (
    get_account,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SESv2",
        {"get_account": ()},
    )

    module.exit_json(
        changed=False,
        account=get_account(client, module),
    )


if __name__ == "__main__":
    main()
