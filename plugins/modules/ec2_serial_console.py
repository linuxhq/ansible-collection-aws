#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_serial_console
version_added: 1.9.1
short_description: Manage EC2 serial console access
description:
  - Enables or disables EC2 serial console access for a region.
author:
  - Taylor Kimball (@tkimball83)
options:
  state:
    description:
      - Whether EC2 serial console access should be enabled.
    choices:
      - absent
      - present
    default: present
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure EC2 serial console access is enabled
  linuxhq.aws.ec2_serial_console:
    region: us-east-1
    state: present

- name: Ensure EC2 serial console access is disabled
  linuxhq.aws.ec2_serial_console:
    region: us-east-1
    state: absent
"""

RETURN = r"""
region:
  description: The AWS region where serial console access was managed.
  returned: always
  type: str
serial_console_access:
  description:
    - The current EC2 serial console access status for the selected region.
  returned: always
  type: dict
state:
  description: The requested state of EC2 serial console access.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    field_differences,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ec2 import (
    get_serial_console_access_status,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    client = module.client("ec2")

    desired_enabled = module.params["state"] == "present"
    current = get_serial_console_access_status(client, module)
    _, changed = field_differences(
        current,
        {"serial_console_access_enabled": desired_enabled},
        ["serial_console_access_enabled"],
    )

    if changed and not module.check_mode:
        operation = (
            "enable_serial_console_access"
            if desired_enabled
            else "disable_serial_console_access"
        )
        aws_response(
            client,
            module,
            operation,
            error_message="Unable to manage EC2 serial console access",
        )
        current = get_serial_console_access_status(client, module)

    result = {
        "changed": changed,
        "region": module.region,
        "serial_console_access": current,
        "state": module.params["state"],
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
