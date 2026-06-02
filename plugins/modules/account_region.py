#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: account_region
short_description: Manage opt-in status of aws account regions
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
      - Default Regions with C(ENABLED_BY_DEFAULT) status cannot be disabled.
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
  wait_delay:
    description:
      - Delay in seconds between status checks when O(wait=true).
    default: 30
    type: int
  wait_timeout:
    description:
      - Maximum number of seconds to wait when O(wait=true).
    default: 1800
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
)

PRESENT_STATUSES = {"ENABLED", "ENABLING", "ENABLED_BY_DEFAULT"}
ABSENT_STATUSES = {"DISABLED", "DISABLING"}
PRESENT_STEADY_STATUSES = {"ENABLED", "ENABLED_BY_DEFAULT"}
ABSENT_STEADY_STATUSES = {"DISABLED"}


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


def get_region(client, module):
    region_name = module.params["name"]

    try:
        return client.get_region_opt_status(
            RegionName=region_name,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS account region opt-in status for {region_name}",
        )


def normalize_region(region):
    if "RegionName" in region or "RegionOptStatus" in region:
        return boto3_resource_to_ansible_dict(
            region,
            transform_tags=False,
            force_tags=False,
        )

    return region


def wait_for_status(client, module, waiter_name, statuses):
    region_name = module.params["name"]

    try:
        waiter = AccountRegionWaiterFactory().get_waiter(client, waiter_name)
        waiter.wait(
            RegionName=region_name,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=max(1, module.params["wait_delay"]),
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                f"Timed out waiting for AWS account region {region_name} "
                f"to reach one of {sorted(statuses)}"
            ),
        )

    return get_region(client, module)


def exit_region(module, previous_region, current_region, changed):
    previous_region = normalize_region(previous_region)
    current_region = normalize_region(current_region)

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        previous_region_opt_status=previous_region.get("region_opt_status"),
        region_opt_status=current_region.get("region_opt_status"),
    )


def ensure_present(client, module):
    region_name = module.params["name"]
    previous_region = get_region(client, module)

    previous_status = normalize_region(previous_region).get("region_opt_status")
    changed = previous_status not in PRESENT_STATUSES

    if changed and not module.check_mode:
        try:
            client.enable_region(
                RegionName=region_name,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to enable AWS account region {region_name}",
            )

    if changed and module.check_mode:
        current_region = {
            "region_name": region_name,
            "region_opt_status": "ENABLED",
        }
    elif (
        module.params["wait"]
        and not module.check_mode
        and (changed or previous_status not in PRESENT_STEADY_STATUSES)
    ):
        current_region = wait_for_status(
            client,
            module,
            "region_enabled",
            PRESENT_STEADY_STATUSES,
        )
    elif changed:
        current_region = get_region(client, module)
    else:
        current_region = previous_region

    exit_region(module, previous_region, current_region, changed)


def ensure_absent(client, module):
    region_name = module.params["name"]
    previous_region = get_region(client, module)

    previous_status = normalize_region(previous_region).get("region_opt_status")

    if previous_status == "ENABLED_BY_DEFAULT":
        module.fail_json(
            msg=(
                f"Unable to disable AWS account region {region_name} "
                "because default Regions cannot be disabled"
            ),
        )

    changed = previous_status not in ABSENT_STATUSES

    if changed and not module.check_mode:
        try:
            client.disable_region(
                RegionName=region_name,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to disable AWS account region {region_name}",
            )

    if changed and module.check_mode:
        current_region = {
            "region_name": region_name,
            "region_opt_status": "DISABLED",
        }
    elif (
        module.params["wait"]
        and not module.check_mode
        and (changed or previous_status not in ABSENT_STEADY_STATUSES)
    ):
        current_region = wait_for_status(
            client,
            module,
            "region_disabled",
            ABSENT_STEADY_STATUSES,
        )
    elif changed:
        current_region = get_region(client, module)
    else:
        current_region = previous_region

    exit_region(module, previous_region, current_region, changed)


def main():
    argument_spec = {
        "name": {"required": True, "type": "str"},
        "state": {
            "choices": ["present", "absent"],
            "default": "present",
            "type": "str",
        },
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 30, "type": "int"},
        "wait_timeout": {"default": 1800, "type": "int"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("account", retry_decorator=AWSRetry.jittered_backoff())

    for method_name in ("get_region_opt_status", "enable_region", "disable_region"):
        try:
            get_boto3_client_method_parameters(client, method_name)
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support AWS Account {method_name}"
            )

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
