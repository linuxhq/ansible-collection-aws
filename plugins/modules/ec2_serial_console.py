#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_serial_console
short_description: Manage aws ec2 serial console access
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
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_serial_console_access_status(client, module):
    try:
        return boto3_resource_to_ansible_dict(
            client.get_serial_console_access_status(aws_retry=True),
            transform_tags=False,
            force_tags=False,
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get EC2 serial console access")


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
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    if state == "present":
        desired_enabled = True
    elif state == "absent":
        desired_enabled = False
    else:
        module.fail_json(msg=f"Unsupported state: {state}")
    desired = {"serial_console_access_enabled": desired_enabled}
    current = get_serial_console_access_status(client, module)
    changed = current.get("serial_console_access_enabled") != desired_enabled

    if changed and not module.check_mode:
        operation = (
            "enable_serial_console_access"
            if desired_enabled
            else "disable_serial_console_access"
        )
        try:
            current = boto3_resource_to_ansible_dict(
                getattr(client, operation)(aws_retry=True),
                transform_tags=False,
                force_tags=False,
            )
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to manage EC2 serial console access")
    elif changed and module.check_mode:
        current = desired

    result = {
        "changed": changed,
        "region": module.region,
        "serial_console_access": current,
        "state": state,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
