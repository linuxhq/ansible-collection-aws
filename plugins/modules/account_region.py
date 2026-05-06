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
  - Compares the desired state against the current region opt-in status fetched by name.
  - O(name) is immutable and identifies the region being managed.
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
    default: true
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    field_differences,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    wait_for_aws_resource,
)

PRESENT_STATUSES = {"ENABLED", "ENABLING", "ENABLED_BY_DEFAULT"}
ABSENT_STATUSES = {"DISABLED", "DISABLING"}
COMPARE_ITEMS = ["name", "state"]


ACCOUNT_REGION_WAITER_MODEL_DATA = {
    "region_enabled": {
        "delay": 30,
        "maxAttempts": 60,
        "operation": "GetRegionOptStatus",
        "acceptors": [
            {
                "argument": "RegionOptStatus",
                "expected": "ENABLED",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "ENABLED_BY_DEFAULT",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "ENABLING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "DISABLING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "DISABLED",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
    "region_disabled": {
        "delay": 30,
        "maxAttempts": 60,
        "operation": "GetRegionOptStatus",
        "acceptors": [
            {
                "argument": "RegionOptStatus",
                "expected": "DISABLED",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "DISABLING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "ENABLING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "ENABLED",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "RegionOptStatus",
                "expected": "ENABLED_BY_DEFAULT",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}


def desired_statuses(state):
    if state == "present":
        return PRESENT_STATUSES
    return ABSENT_STATUSES


def ensure_region(client, module):
    desired = {
        "name": module.params["name"],
        "state": module.params["state"],
    }
    previous = normalize_account_region(
        desired["name"],
        get_region_opt_status(client, module, desired["name"]),
    )
    current = (
        {"name": previous["name"], "state": previous["state"]}
        if previous is not None
        else None
    )

    if current is None:
        changed = True
    else:
        _, changed = field_differences(
            current,
            desired,
            COMPARE_ITEMS,
        )

    if changed and not module.check_mode:
        update_region_state(client, module, desired)
        current_status = (
            wait_for_status(
                client,
                module,
                desired["name"],
                desired_statuses(desired["state"]),
            )
            if module.params["wait"]
            else get_region_opt_status(client, module, desired["name"])
        )
        current_region = normalize_account_region(desired["name"], current_status)
    elif changed and module.check_mode:
        current_region = {
            "name": desired["name"],
            "region_opt_status": (
                "ENABLED" if desired["state"] == "present" else "DISABLED"
            ),
            "state": desired["state"],
        }
    else:
        current_region = previous

    if module.params["wait"] and not module.check_mode and not changed:
        current_region = normalize_account_region(
            desired["name"],
            wait_for_status(
                client,
                module,
                desired["name"],
                desired_statuses(desired["state"]),
            ),
        )

    module.exit_json(
        changed=changed,
        name=desired["name"],
        previous_region_opt_status=(
            previous["region_opt_status"] if previous is not None else None
        ),
        region_opt_status=(
            current_region["region_opt_status"] if current_region is not None else None
        ),
    )


def get_region_opt_status(client, module, region_name):
    return aws_resource(
        client,
        module,
        "get_region_opt_status",
        "RegionOptStatus",
        RegionName=region_name,
    )


def normalize_account_region(name, region_opt_status):
    if not region_opt_status:
        return None
    if region_opt_status in PRESENT_STATUSES:
        state = "present"
    elif region_opt_status in ABSENT_STATUSES:
        state = "absent"
    else:
        state = None
    return {
        "name": name,
        "region_opt_status": region_opt_status,
        "state": state,
    }


def update_region_state(client, module, desired):
    region_name = desired["name"]

    if desired["state"] == "present":
        operation = "enable_region"
        action = "enable"
    else:
        operation = "disable_region"
        action = "disable"

    aws_response(
        client,
        module,
        operation,
        error_message=f"Unable to {action} AWS account region {region_name}",
        RegionName=region_name,
    )


def wait_for_status(client, module, region_name, desired_statuses):
    waiter_name = (
        "region_enabled" if desired_statuses == PRESENT_STATUSES else "region_disabled"
    )
    wait_for_aws_resource(
        client,
        module,
        ACCOUNT_REGION_WAITER_MODEL_DATA,
        waiter_name,
        (
            f"Timed out waiting for AWS account region {region_name} "
            f"to reach one of {sorted(desired_statuses)}"
        ),
        waiter_config={
            "Delay": module.params["delay"],
            "MaxAttempts": module.params["retries"],
        },
        RegionName=region_name,
    )
    return get_region_opt_status(client, module, region_name)


def main():
    argument_spec = {
        "name": {"required": True, "type": "str"},
        "state": {
            "choices": ["present", "absent"],
            "default": "present",
            "type": "str",
        },
        "wait": {"default": True, "type": "bool"},
        "delay": {"default": 30, "type": "int"},
        "retries": {"default": 60, "type": "int"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("account")

    ensure_region(client, module)


if __name__ == "__main__":
    main()
