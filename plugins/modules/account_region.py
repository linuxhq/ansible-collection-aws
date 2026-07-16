#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - This must be 1 or greater.
    default: 30
    type: int
  wait_timeout:
    description:
      - Maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
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
previous_region_opt_status:
  description: The AWS region opt-in status before any change was requested.
  returned: always
  type: str
region_opt_status:
  description: The current AWS region opt-in status.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
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


def get_region_opt_status(client, module):
    region_name = module.params["name"]

    try:
        return client.get_region_opt_status(
            RegionName=region_name,
            aws_retry=True,
        ).get("RegionOptStatus")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS account region opt-in status for {region_name}",
        )


def wait_for_status(client, module, waiter_name, statuses):
    region_name = module.params["name"]

    run_waiter(
        module,
        client,
        ACCOUNT_REGION_WAITER_MODEL_DATA,
        waiter_name,
        (
            f"Timed out waiting for AWS account region {region_name} "
            f"to reach one of {sorted(statuses)}"
        ),
        RegionName=region_name,
    )

    return get_region_opt_status(client, module)


def exit_region(module, previous_status, current_status, changed):
    module.exit_json(
        changed=changed,
        name=module.params["name"],
        previous_region_opt_status=previous_status,
        region_opt_status=current_status,
    )


def ensure_present(client, module):
    region_name = module.params["name"]
    previous_status = get_region_opt_status(client, module)

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
        current_status = "ENABLED"
    elif (
        module.params["wait"]
        and not module.check_mode
        and (changed or previous_status not in PRESENT_STEADY_STATUSES)
    ):
        current_status = wait_for_status(
            client,
            module,
            "region_enabled",
            PRESENT_STEADY_STATUSES,
        )
    elif changed:
        current_status = get_region_opt_status(client, module)
    else:
        current_status = previous_status

    exit_region(module, previous_status, current_status, changed)


def ensure_absent(client, module):
    region_name = module.params["name"]
    previous_status = get_region_opt_status(client, module)

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
        current_status = "DISABLED"
    elif (
        module.params["wait"]
        and not module.check_mode
        and (changed or previous_status not in ABSENT_STEADY_STATUSES)
    ):
        current_status = wait_for_status(
            client,
            module,
            "region_disabled",
            ABSENT_STEADY_STATUSES,
        )
    elif changed:
        current_status = get_region_opt_status(client, module)
    else:
        current_status = previous_status

    exit_region(module, previous_status, current_status, changed)


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

    require_positive_wait_bounds(module)

    client = module.client("account", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    methods = {"get_region_opt_status": ()}
    if state == "present":
        methods["enable_region"] = ()

    if state == "absent":
        methods["disable_region"] = ()

    require_client_methods(module, client, "AWS Account", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
