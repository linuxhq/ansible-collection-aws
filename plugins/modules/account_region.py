#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: account_region
version_added: 1.9.1
short_description: Manage AWS account region opt-in status
description:
  - Enables or disables the opt-in status of an AWS account region.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The AWS region name to manage.
    required: true
    type: str
  state:
    description:
      - Desired opt-in status for the region.
    choices:
      - present
      - absent
    default: present
    type: str
  wait:
    description:
      - Wait for the region status to reach the desired steady state.
    default: false
    type: bool
  delay:
    description:
      - Delay in seconds between status checks when O(wait=true).
    default: 30
    type: int
  retries:
    description:
      - Maximum number of status checks when O(wait=true).
    default: 60
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Enable an opt-in region
  linuxhq.aws.account_region:
    name: af-south-1
    state: present

- name: Disable an opt-in region
  linuxhq.aws.account_region:
    name: af-south-1
    state: absent
"""

RETURN = r"""
name:
  description: The AWS region name that was managed.
  returned: always
  type: str
region_opt_status:
  description: The current AWS region opt-in status.
  returned: always
  type: str
previous_region_opt_status:
  description: The AWS region opt-in status before any change was requested.
  returned: always
  type: str
"""

import time

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule

PRESENT_STATUSES = {"ENABLED", "ENABLING", "ENABLED_BY_DEFAULT"}
ABSENT_STATUSES = {"DISABLED", "DISABLING"}


def get_region_opt_status(client, module, region_name):
    try:
        response = client.get_region_opt_status(RegionName=region_name)
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to get AWS account region opt-in status for {region_name}"
        )
    return response["RegionOptStatus"]


def wait_for_status(client, module, region_name, desired_statuses):
    for _ in range(module.params["retries"]):
        status = get_region_opt_status(client, module, region_name)
        if status in desired_statuses:
            return status
        time.sleep(module.params["delay"])
    module.fail_json(
        msg=f"Timed out waiting for AWS account region {region_name} to reach one of {sorted(desired_statuses)}",
        region_opt_status=status,
    )


def main():
    argument_spec = {
        "name": {"required": True, "type": "str"},
        "state": {
            "choices": ["present", "absent"],
            "default": "present",
            "type": "str",
        },
        "wait": {"default": False, "type": "bool"},
        "delay": {"default": 30, "type": "int"},
        "retries": {"default": 60, "type": "int"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("account")

    region_name = module.params["name"]
    state = module.params["state"]
    previous_status = get_region_opt_status(client, module, region_name)
    current_status = previous_status
    changed = False

    if state == "present" and previous_status == "DISABLED":
        changed = True
        if not module.check_mode:
            try:
                client.enable_region(RegionName=region_name)
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to enable AWS account region {region_name}"
                )
            current_status = (
                wait_for_status(client, module, region_name, PRESENT_STATUSES)
                if module.params["wait"]
                else get_region_opt_status(client, module, region_name)
            )
    elif state == "absent" and previous_status == "ENABLED":
        changed = True
        if not module.check_mode:
            try:
                client.disable_region(RegionName=region_name)
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to disable AWS account region {region_name}"
                )
            current_status = (
                wait_for_status(client, module, region_name, ABSENT_STATUSES)
                if module.params["wait"]
                else get_region_opt_status(client, module, region_name)
            )
    elif module.params["wait"] and not module.check_mode:
        if state == "present" and previous_status == "ENABLING":
            current_status = wait_for_status(
                client, module, region_name, PRESENT_STATUSES
            )
        elif state == "absent" and previous_status == "DISABLING":
            current_status = wait_for_status(
                client, module, region_name, ABSENT_STATUSES
            )

    module.exit_json(
        changed=changed,
        name=region_name,
        previous_region_opt_status=previous_status,
        region_opt_status=current_status,
    )


if __name__ == "__main__":
    main()
