#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: account_region
version_added: "1.9.0"
short_description: Manage opt-in status of AWS account regions
description:
  - Enables or disables the opt-in status of an AWS account region.
  - Compares the desired state against the current region opt-in status fetched by name.
  - Before requesting a change, fails if AWS returns an unrecognized region opt-in status.
author:
  - Taylor Kimball (@tkimball83)
options:
  account_id:
    description:
      - The 12-digit ID of a member account in the same organization.
      - Omit to use the account of the calling identity, including a management account.
      - Cross-account access requires organization management or delegated administrator credentials,
        all organization features, and trusted access for Account Management.
      - Requires botocore 1.29.70 or later.
    type: str
    version_added: "2.6.0"
  name:
    description:
      - The AWS region name to manage.
      - Requires botocore 1.29.70 or later.
    required: true
    type: str
  state:
    description:
      - Desired opt-in status for the region.
      - Default Regions with C(ENABLED_BY_DEFAULT) status cannot be disabled.
      - Requires botocore 1.29.70 or later.
    choices:
      - present
      - absent
    default: present
    type: str
  wait:
    description:
      - Wait for the region status to reach the desired steady state.
      - Even when O(wait=false), a pending opposite transition is always awaited before the region is
        enabled or disabled, C(DISABLING) when O(state=present) and C(ENABLING) when O(state=absent).
        This wait uses O(wait_delay) and is bounded by O(wait_timeout).
    default: true
    type: bool
  wait_delay:
    description:
      - Delay in seconds between status checks when O(wait=true) or while a pending opposite
        transition is awaited.
      - This must be 1 or greater.
    default: 30
    type: int
  wait_timeout:
    description:
      - Maximum number of seconds to wait when O(wait=true).
      - Also bounds the wait for a pending opposite transition, which happens even when O(wait=false).
      - This must be 1 or greater.
    default: 1800
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Returns the predicted changed status without modifying the account region.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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

- name: Enable an opt-in region for a member account
  linuxhq.aws.account_region:
    account_id: "123456789012"
    name: af-south-1
    state: present
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

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.account import account_parameters
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
)

PRESENT_STATUSES = {"ENABLED", "ENABLING", "ENABLED_BY_DEFAULT"}
ABSENT_STATUSES = {"DISABLED", "DISABLING"}
REGION_OPT_STATUSES = PRESENT_STATUSES | ABSENT_STATUSES
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


def region_request(module):
    return dict(account_parameters(module), RegionName=module.params["name"])


def region_target(module):
    account_id = module.params.get("account_id")
    name = module.params["name"]
    return f"{name} in account {account_id}" if account_id else name


def get_region_opt_status(client, module, changed=False):
    region_name = region_target(module)

    try:
        response = client.get_region_opt_status(
            **region_request(module),
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            changed=changed,
            msg=f"Unable to get AWS account region opt-in status for {region_name}",
        )

    region_status = response.get("RegionOptStatus")
    if region_status not in REGION_OPT_STATUSES:
        module.fail_json(
            changed=changed,
            msg=(
                f"Unable to get AWS account region opt-in status for {region_name}: "
                f"unexpected status {region_status!r}"
            ),
        )

    return region_status


def wait_for_status(client, module, waiter_name, statuses, changed=False):
    region_name = region_target(module)

    run_waiter(
        module,
        client,
        ACCOUNT_REGION_WAITER_MODEL_DATA,
        waiter_name,
        f"Timed out waiting for AWS account region {region_name} to reach one of {sorted(statuses)}",
        changed=changed,
        **region_request(module),
    )

    return get_region_opt_status(client, module, changed=changed)


def exit_region(module, previous_status, current_status, changed):
    module.exit_json(
        changed=changed,
        name=module.params["name"],
        previous_region_opt_status=previous_status,
        region_opt_status=current_status,
    )


def ensure_present(client, module):
    region_name = region_target(module)
    previous_status = get_region_opt_status(client, module)

    changed = previous_status not in PRESENT_STATUSES

    if changed and not module.check_mode:
        if previous_status == "DISABLING":
            wait_for_status(client, module, "region_disabled", ABSENT_STEADY_STATUSES)

        require_client_methods(
            module,
            client,
            "AWS Account",
            {"enable_region": tuple(region_request(module))},
        )
        try:
            client.enable_region(
                **region_request(module),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to enable AWS account region {region_name}",
            )

    if changed and module.check_mode:
        current_status = "ENABLED"
    elif (
        module.params["wait"] and not module.check_mode and (changed or previous_status not in PRESENT_STEADY_STATUSES)
    ):
        current_status = wait_for_status(
            client,
            module,
            "region_enabled",
            PRESENT_STEADY_STATUSES,
            changed=changed,
        )
    elif changed:
        current_status = get_region_opt_status(client, module, changed=True)
    else:
        current_status = previous_status

    exit_region(module, previous_status, current_status, changed)


def ensure_absent(client, module):
    region_name = region_target(module)
    previous_status = get_region_opt_status(client, module)

    if previous_status == "ENABLED_BY_DEFAULT":
        module.fail_json(
            msg=f"Unable to disable AWS account region {region_name} because default Regions cannot be disabled",
        )

    changed = previous_status not in ABSENT_STATUSES

    if changed and not module.check_mode:
        if previous_status == "ENABLING":
            wait_for_status(client, module, "region_enabled", PRESENT_STEADY_STATUSES)

        require_client_methods(
            module,
            client,
            "AWS Account",
            {"disable_region": tuple(region_request(module))},
        )
        try:
            client.disable_region(
                **region_request(module),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to disable AWS account region {region_name}",
            )

    if changed and module.check_mode:
        current_status = "DISABLED"
    elif module.params["wait"] and not module.check_mode and (changed or previous_status not in ABSENT_STEADY_STATUSES):
        current_status = wait_for_status(
            client,
            module,
            "region_disabled",
            ABSENT_STEADY_STATUSES,
            changed=changed,
        )
    elif changed:
        current_status = get_region_opt_status(client, module, changed=True)
    else:
        current_status = previous_status

    exit_region(module, previous_status, current_status, changed)


def main():
    argument_spec = {
        "account_id": {"type": "str"},
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

    require_positive_wait_bounds(module, always=True)
    request = region_request(module)

    client = module.client("account", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    require_client_methods(
        module,
        client,
        "AWS Account",
        {"get_region_opt_status": tuple(request)},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
