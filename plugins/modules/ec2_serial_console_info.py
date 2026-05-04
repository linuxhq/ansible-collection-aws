#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_serial_console_info
version_added: 1.9.1
short_description: Gather EC2 serial console access status
description:
  - Gathers EC2 serial console access status for a region.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather EC2 serial console access status
  linuxhq.aws.ec2_serial_console_info:
    region: us-east-1
"""

RETURN = r"""
region:
  description: The AWS region where serial console access was gathered.
  returned: always
  type: str
serial_console_access:
  description:
    - The current EC2 serial console access status for the selected region.
  returned: always
  type: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.ec2 import (
    get_serial_console_access,
    normalize_serial_console_access,
)


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("ec2")

    module.exit_json(
        changed=False,
        region=module.region,
        serial_console_access=normalize_serial_console_access(
            get_serial_console_access(client, module)
        ),
    )


if __name__ == "__main__":
    main()
