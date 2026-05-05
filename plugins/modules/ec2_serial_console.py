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
    aws_resource_to_snake_dict,
)


def get_serial_console_access(client, module):
    response = aws_response(client, module, "get_serial_console_access_status")
    status = {
        "ManagedBy": response.get("ManagedBy"),
        "SerialConsoleAccessEnabled": response.get("SerialConsoleAccessEnabled"),
    }
    return {key: value for key, value in status.items() if value is not None}


def set_serial_console_access(client, module, desired_enabled):
    aws_response(
        client,
        module,
        (
            "enable_serial_console_access"
            if desired_enabled
            else "disable_serial_console_access"
        ),
        error_message="Unable to manage EC2 serial console access",
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
    current = get_serial_console_access(client, module)
    changed = current.get("SerialConsoleAccessEnabled") != desired_enabled

    if changed and not module.check_mode:
        set_serial_console_access(client, module, desired_enabled)
        current = get_serial_console_access(client, module)

    result = {
        "changed": changed,
        "region": module.region,
        "serial_console_access": aws_resource_to_snake_dict(current),
        "state": module.params["state"],
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
