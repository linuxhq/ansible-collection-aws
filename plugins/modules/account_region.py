#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: account_region
version_added: "1.9.5"
short_description: Manage AWS account region opt-in status
description:
  - Enables or disables the opt-in status of an AWS account region.
  - Compares the desired state against the current region opt-in status fetched by name.
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

from ansible.module_utils.common.dict_transformations import (
    recursive_diff,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
)

PRESENT_STATUSES = {"ENABLED", "ENABLING", "ENABLED_BY_DEFAULT"}
ABSENT_STATUSES = {"DISABLED", "DISABLING"}


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


class AccountRegionWaiterFactory(BaseWaiterFactory):
    @property
    def _waiter_model_data(self):
        return ACCOUNT_REGION_WAITER_MODEL_DATA


def get_region(client, module, region_name):
    try:
        return client.get_region_opt_status(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {"region_name": region_name}, capitalize_first=True
                )
            ),
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS account region opt-in status for {region_name}",
        )


def wait_for_status(client, module, region_name, statuses):
    waiter_name = (
        "region_enabled" if statuses == PRESENT_STATUSES else "region_disabled"
    )
    try:
        waiter = AccountRegionWaiterFactory().get_waiter(client, waiter_name)
        waiter.wait(
            RegionName=region_name,
            WaiterConfig={
                "Delay": module.params["delay"],
                "MaxAttempts": module.params["retries"],
            },
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                f"Timed out waiting for AWS account region {region_name} "
                f"to reach one of {sorted(statuses)}"
            ),
        )
    return get_region(client, module, region_name)


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
    client = module.client("account", retry_decorator=AWSRetry.jittered_backoff())

    region_name = module.params["name"]
    state = module.params["state"]
    statuses = PRESENT_STATUSES if state == "present" else ABSENT_STATUSES
    previous = get_region(client, module, region_name)
    previous_region = boto3_resource_to_ansible_dict(
        previous, transform_tags=False, force_tags=False
    )
    previous_status = previous_region.get("region_opt_status")
    target_status = previous_status if previous_status in statuses else "ENABLED"
    if state == "absent" and previous_status not in statuses:
        target_status = "DISABLED"

    current = {
        "region_name": previous_region.get("region_name"),
        "region_opt_status": previous_region.get("region_opt_status"),
    }
    desired = {
        "region_name": region_name,
        "region_opt_status": target_status,
    }
    changed = recursive_diff(current, desired) is not None

    if changed and not module.check_mode:
        operation = "enable_region" if state == "present" else "disable_region"
        action = "enable" if state == "present" else "disable"
        try:
            getattr(client, operation)(
                **scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {"region_name": region_name}, capitalize_first=True
                    )
                ),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to {action} AWS account region {region_name}"
            )
        current_region = (
            wait_for_status(client, module, region_name, statuses)
            if module.params["wait"]
            else get_region(client, module, region_name)
        )
    elif changed and module.check_mode:
        current_region = desired
    else:
        current_region = previous

    if module.params["wait"] and not module.check_mode and not changed:
        current_region = wait_for_status(client, module, region_name, statuses)

    module.exit_json(
        changed=changed,
        name=region_name,
        previous_region_opt_status=previous_status,
        region_opt_status=boto3_resource_to_ansible_dict(
            current_region, transform_tags=False, force_tags=False
        ).get("region_opt_status"),
    )


if __name__ == "__main__":
    main()
