#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox_info
version_added: 1.9.1
short_description: Gather information about AWS Simple Email Service account details
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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def main() -> None:
    module = AnsibleAWSModule(
        argument_spec={"validate_certs": {"default": True, "type": "bool"}},
        supports_check_mode=True,
    )
    client = module.client("sesv2")

    try:
        response = client.get_account()
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to get AWS Simple Email Service account details"
        )

    module.exit_json(changed=False, account=camel_dict_to_snake_dict(response))


if __name__ == "__main__":
    main()
