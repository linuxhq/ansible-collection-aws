#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_metadata_info
version_added: 1.9.1
short_description: Gather EC2 account-level instance metadata defaults
description:
  - Gathers EC2 account-level instance metadata defaults for a region.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather EC2 account-level instance metadata defaults
  linuxhq.aws.ec2_instance_metadata_info:
    region: us-east-1
"""

RETURN = r"""
account_level:
  description:
    - The current account-level EC2 instance metadata defaults for the selected region.
  returned: always
  type: dict
region:
  description: The AWS region where the defaults were gathered.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.ec2 import (
    get_instance_metadata_defaults,
)


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("ec2")

    module.exit_json(
        changed=False,
        account_level=get_instance_metadata_defaults(client, module),
        region=module.region,
    )


if __name__ == "__main__":
    main()
