#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_send_command
short_description: Send AWS Systems Manager commands
description:
  - Sends an AWS Systems Manager Run Command request.
  - Optionally waits for command invocations to complete.
  - This module is inherently non-idempotent because every execution sends a
    new command.
author:
  - Taylor Kimball (@tkimball83)
options:
  comment:
    description:
      - A comment for the command.
    type: str
  document_name:
    description:
      - The Systems Manager document name to execute.
      - This must not be empty.
    required: true
    type: str
  instance_ids:
    description:
      - A list of instance IDs to target directly.
      - Entries must not be empty.
      - This must contain at most 50 entries.
      - At least one of O(instance_ids) or O(targets) is required.
      - Mutually exclusive with O(targets).
    elements: str
    type: list
  max_concurrency:
    description:
      - The maximum number of managed nodes that are allowed to run the command at the same time.
    type: str
  max_errors:
    description:
      - The maximum number of errors allowed before the command stops sending to additional targets.
    type: str
  parameters:
    description:
      - The document parameters to pass to the command.
    default: {}
    type: dict
  targets:
    description:
      - The command targets.
      - This must contain at most 5 entries.
      - The value of O(targets[].key) is sent to AWS unchanged. Use an AWS
        target key such as C(InstanceIds) or C(tag:Name).
      - Each target requires a target key and values.
      - At least one of O(instance_ids) or O(targets) is required.
      - Mutually exclusive with O(instance_ids).
    elements: dict
    suboptions:
      key:
        description:
          - The target key.
          - This must be 1 to 163 characters.
        required: true
        type: str
      values:
        description:
          - The target values.
          - This must contain at most 50 entries.
        elements: str
        required: true
        type: list
    type: list
  timeout_seconds:
    description:
      - The timeout in seconds for the command execution.
      - This must be between 30 and 2592000.
    type: int
  wait:
    description:
      - Whether to wait for command invocations to complete.
      - When O(wait=true), the module fails unless every invocation succeeds,
        regardless of O(max_errors).
    default: false
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    default: 600
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: The module validates its inputs and reports that the command would be sent.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Ensure a shell command is executed
  linuxhq.aws.ssm_send_command:
    document_name: AWS-RunShellScript
    parameters:
      commands:
        - touch /tmp/molecule
    targets:
      - key: InstanceIds
        values:
          - i-0123456789abcdef0
    wait: true
"""

RETURN = r"""
command:
  description:
    - The command metadata returned by AWS Systems Manager.
  returned: when not in check mode
  type: dict
  contains:
    alarm_configuration:
      description: Alarm configuration associated with the command.
      returned: when available
      type: dict
    cloud_watch_output_config:
      description: CloudWatch Logs output configuration for the command.
      returned: when available
      type: dict
    command_id:
      description: Command ID assigned by AWS Systems Manager.
      returned: when available
      type: str
    comment:
      description: Comment associated with the command.
      returned: when available
      type: str
    completed_count:
      description: Number of targets that completed the command.
      returned: when available
      type: int
    delivery_timed_out_count:
      description: Number of command deliveries that timed out.
      returned: when available
      type: int
    document_name:
      description: Name of the document used by the command.
      returned: when available
      type: str
    document_version:
      description: Version of the document used by the command.
      returned: when available
      type: str
    error_count:
      description: Number of targets on which the command failed.
      returned: when available
      type: int
    expires_after:
      description: Time after which the command is not invoked.
      returned: when available
      type: str
    instance_ids:
      description: Instance IDs targeted directly by the command.
      returned: when available
      type: list
      elements: str
    max_concurrency:
      description: Maximum number of targets allowed to run concurrently.
      returned: when available
      type: str
    max_errors:
      description: Maximum number of errors allowed before dispatch stops.
      returned: when available
      type: str
    notification_config:
      description: Notification configuration for the command.
      returned: when available
      type: dict
    output_s3_bucket_name:
      description: S3 bucket used for command output.
      returned: when available
      type: str
    output_s3_key_prefix:
      description: S3 key prefix used for command output.
      returned: when available
      type: str
    output_s3_region:
      description: AWS region containing the command output bucket.
      returned: when available
      type: str
    parameters:
      description:
        - The document parameters sent with the command.
        - Parameter names are returned unchanged, so they keep the casing AWS
          reports rather than being converted to snake_case.
      returned: when available
      type: dict
    requested_date_time:
      description: Time when the command was requested.
      returned: when available
      type: str
    service_role:
      description: IAM service role used for notifications.
      returned: when available
      type: str
    status:
      description: Command status.
      returned: when available
      type: str
    status_details:
      description: Detailed command status.
      returned: when available
      type: str
    target_count:
      description: Number of targets for the command.
      returned: when available
      type: int
    targets:
      description:
        - The command targets as returned by AWS.
        - The target wrapper keys remain C(Key) and C(Values) for backward
          compatibility.
      returned: when available
      type: list
      elements: dict
    timeout_seconds:
      description: Command execution timeout in seconds.
      returned: when available
      type: int
    triggered_alarms:
      description: Alarms triggered while the command ran.
      returned: when available
      type: list
      elements: dict
command_id:
  description:
    - The AWS Systems Manager command ID.
  returned: when not in check mode
  type: str
command_invocations:
  description:
    - The command invocations returned when O(wait=true).
  returned: when wait is true and not in check mode
  type: list
  elements: dict
  contains:
    cloud_watch_output_config:
      description: CloudWatch Logs output configuration for the invocation.
      returned: when available
      type: dict
    command_id:
      description: Command ID associated with the invocation.
      returned: when available
      type: str
    command_plugins:
      description: Results returned by the command's plugins.
      returned: when available
      type: list
      elements: dict
      contains:
        name:
          description: Plugin name.
          returned: when available
          type: str
        output:
          description: Plugin output.
          returned: when available
          type: str
        output_s3_bucket_name:
          description: S3 bucket containing plugin output.
          returned: when available
          type: str
        output_s3_key_prefix:
          description: S3 key prefix containing plugin output.
          returned: when available
          type: str
        output_s3_region:
          description: AWS region containing the plugin output bucket.
          returned: when available
          type: str
        response_code:
          description: Response code returned by the plugin.
          returned: when available
          type: int
        response_finish_date_time:
          description: Time when the plugin response finished.
          returned: when available
          type: str
        response_start_date_time:
          description: Time when the plugin response started.
          returned: when available
          type: str
        standard_error_url:
          description: URL containing the plugin's standard error output.
          returned: when available
          type: str
        standard_output_url:
          description: URL containing the plugin's standard output.
          returned: when available
          type: str
        status:
          description: Plugin status.
          returned: when available
          type: str
        status_details:
          description: Detailed plugin status.
          returned: when available
          type: str
    comment:
      description: Comment associated with the invocation.
      returned: when available
      type: str
    document_name:
      description: Name of the document used by the command.
      returned: when available
      type: str
    document_version:
      description: Version of the document used by the invocation.
      returned: when available
      type: str
    instance_id:
      description: Managed instance ID associated with the invocation.
      returned: when available
      type: str
    instance_name:
      description: Name of the managed instance associated with the invocation.
      returned: when available
      type: str
    notification_config:
      description: Notification configuration for the invocation.
      returned: when available
      type: dict
    requested_date_time:
      description: Time when the command was requested.
      returned: when available
      type: str
    service_role:
      description: IAM service role used for invocation notifications.
      returned: when available
      type: str
    standard_error_url:
      description: URL containing the invocation's standard error output.
      returned: when available
      type: str
    standard_output_url:
      description: URL containing the invocation's standard output.
      returned: when available
      type: str
    status:
      description: Invocation status.
      returned: when available
      type: str
    status_details:
      description: Detailed invocation status.
      returned: when available
      type: str
    trace_output:
      description: Trace output returned for the invocation.
      returned: when available
      type: str
status:
  description:
    - The aggregate command status.
  returned: when not in check mode
  type: str
"""

import time

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
)

SUCCESS_STATUSES = {"Success"}
TERMINAL_STATUSES = {"Cancelled", "Failed", "Success", "TimedOut"}
SEND_COMMAND_OPTIONS = [
    "comment",
    "instance_ids",
    "max_concurrency",
    "max_errors",
    "timeout_seconds",
]


def is_populated_status_invalid(status):
    """Return True for a present, non-string or empty status; None means not yet populated."""
    return status is not None and (not isinstance(status, str) or not status)


def normalize_command(command):
    return boto3_resource_to_ansible_dict(
        command,
        ignore_list=[
            "Parameters",
            "Targets",
        ],
        transform_tags=False,
        force_tags=False,
    )


def main():
    argument_spec = {
        "comment": {"type": "str"},
        "document_name": {"required": True, "type": "str"},
        "instance_ids": {"elements": "str", "type": "list"},
        "max_concurrency": {"type": "str"},
        "max_errors": {"type": "str"},
        "parameters": {"default": {}, "type": "dict"},
        "targets": {
            "elements": "dict",
            "options": {
                "key": {"no_log": False, "required": True, "type": "str"},
                "values": {"elements": "str", "required": True, "type": "list"},
            },
            "type": "list",
        },
        "timeout_seconds": {"type": "int"},
        "wait": {"default": False, "type": "bool"},
        "wait_delay": {"default": 5, "type": "int"},
        "wait_timeout": {"default": 600, "type": "int"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["instance_ids", "targets"]],
        required_one_of=[["instance_ids", "targets"]],
        supports_check_mode=True,
    )

    document_name = module.params["document_name"]
    if not document_name:
        module.fail_json(msg="document_name must not be empty")

    timeout_seconds = module.params["timeout_seconds"]
    instance_ids = list(dict.fromkeys(module.params["instance_ids"] or []))
    targets = [
        {"key": key, "values": list(values)}
        for key, values in dict.fromkeys(
            (target["key"], tuple(dict.fromkeys(target["values"]))) for target in module.params["targets"] or []
        )
    ]
    if timeout_seconds is not None and not 30 <= timeout_seconds <= 2592000:
        module.fail_json(msg="timeout_seconds must be between 30 and 2592000")
    if not instance_ids and not targets:
        module.fail_json(msg="instance_ids or targets must contain at least one entry")
    if len(instance_ids) > 50:
        module.fail_json(msg="instance_ids must contain at most 50 entries")
    if any(not instance_id for instance_id in instance_ids):
        module.fail_json(msg="instance_ids must not contain empty entries")
    if len(targets) > 5:
        module.fail_json(msg="targets must contain at most 5 entries")
    for target in targets:
        if not target["key"] or not 1 <= len(target["key"]) <= 163:
            module.fail_json(msg="targets[].key must be 1 to 163 characters")
        if not target["values"]:
            module.fail_json(msg="targets[].values must contain at least one entry")
        if len(target["values"]) > 50:
            module.fail_json(msg="targets[].values must contain at most 50 entries")

    require_positive_wait_bounds(module)

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    parameters = module.params["parameters"]
    wait = module.params["wait"]
    send_command_request = {option: module.params[option] for option in SEND_COMMAND_OPTIONS}
    send_command_request["document_name"] = document_name
    send_command_request["instance_ids"] = instance_ids or None
    send_command_request["parameters"] = parameters
    send_command_request["targets"] = targets or None
    send_command_args = scrub_none_parameters(snake_dict_to_camel_dict(send_command_request, capitalize_first=True))
    send_command_args["Parameters"] = parameters

    methods = {"send_command": tuple(send_command_args)}
    if wait:
        methods["list_commands"] = ("CommandId",)
        methods["list_command_invocations"] = ("CommandId", "Details")

    require_client_methods(module, client, "Systems Manager", methods)

    if module.check_mode:
        module.exit_json(changed=True)

    try:
        response = client.send_command(**send_command_args, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=("Unable to send AWS Systems Manager command using " f"{document_name}"),
        )

    command = response.get("Command", {}) if isinstance(response, dict) else None
    if not isinstance(command, dict):
        module.fail_json(
            changed=True,
            msg=f"Unexpected response while sending AWS Systems Manager command using {document_name}",
        )

    command_id = command.get("CommandId")
    if not isinstance(command_id, str) or not command_id:
        module.fail_json(
            changed=True,
            msg=("AWS Systems Manager did not return an ID for the command using " f"{document_name}"),
        )

    command_status = command.get("Status")
    if is_populated_status_invalid(command_status):
        module.fail_json(
            changed=True,
            msg=f"AWS Systems Manager command {command_id} did not return a valid status",
            command=normalize_command(command),
            command_id=command_id,
            status=command_status,
        )

    result = {
        "changed": True,
        "command": normalize_command(command),
        "command_id": command_id,
        "status": command_status,
    }

    if wait:
        wait_delay = module.params["wait_delay"]
        deadline = time.monotonic() + module.params["wait_timeout"]
        invocations = []

        while time.monotonic() < deadline:
            try:
                commands_response = paginated_query_with_retries(
                    client,
                    "list_commands",
                    CommandId=command_id,
                )
                invocations_response = paginated_query_with_retries(
                    client,
                    "list_command_invocations",
                    CommandId=command_id,
                    Details=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    changed=True,
                    msg=f"Unable to get AWS Systems Manager command {command_id}",
                )

            commands = commands_response.get("Commands", []) if isinstance(commands_response, dict) else None
            invocations = (
                invocations_response.get("CommandInvocations", []) if isinstance(invocations_response, dict) else None
            )
            if not isinstance(commands, list):
                module.fail_json(
                    changed=True,
                    msg=(
                        f"Unexpected response while getting AWS Systems Manager command {command_id}; "
                        "Commands was not a list"
                    ),
                )
            if not isinstance(invocations, list):
                module.fail_json(
                    changed=True,
                    msg=(
                        f"Unexpected response while getting AWS Systems Manager command {command_id}; "
                        "CommandInvocations was not a list"
                    ),
                )
            for index, invocation in enumerate(invocations):
                if not isinstance(invocation, dict):
                    module.fail_json(
                        changed=True,
                        msg=(
                            f"Unexpected response while getting AWS Systems Manager command {command_id}; "
                            f"invocation {index} was not a dictionary"
                        ),
                    )

            if not commands:
                module.fail_json(
                    changed=True,
                    msg=(f"AWS Systems Manager command {command_id} was not returned " "by list_commands"),
                )

            command = commands[0]
            if not isinstance(command, dict):
                module.fail_json(
                    changed=True,
                    msg=(
                        f"Unexpected response while getting AWS Systems Manager command {command_id}; "
                        "command 0 was not a dictionary"
                    ),
                )
            command_status = command.get("Status")
            if is_populated_status_invalid(command_status):
                module.fail_json(
                    changed=True,
                    msg=(
                        f"AWS Systems Manager command {command_id} was returned by list_commands "
                        "with an invalid status"
                    ),
                    command=normalize_command(command),
                    command_id=command_id,
                    command_invocations=boto3_resource_list_to_ansible_dict(
                        invocations, transform_tags=False, force_tags=False
                    ),
                    status=command_status,
                )

            # AWS can expose an invocation before populating its status. Retry
            # missing statuses, but reject values that cannot become valid
            # through another poll.
            invocation_statuses = [invocation.get("Status") for invocation in invocations]
            for index, status in enumerate(invocation_statuses):
                if is_populated_status_invalid(status):
                    module.fail_json(
                        changed=True,
                        msg=(
                            f"AWS Systems Manager command {command_id} returned invocation {index} "
                            "without a valid status"
                        ),
                        command=normalize_command(command),
                        command_id=command_id,
                        command_invocations=boto3_resource_list_to_ansible_dict(
                            invocations, transform_tags=False, force_tags=False
                        ),
                        status=command_status,
                    )

            if command_status in TERMINAL_STATUSES and not invocations:
                if command_status in SUCCESS_STATUSES and command.get("TargetCount") == 0:
                    module.warn(
                        f"AWS Systems Manager command {command_id} completed " "without invocations; no targets matched"
                    )
                    break

                if command_status not in SUCCESS_STATUSES:
                    module.fail_json(
                        changed=True,
                        msg=(f"AWS Systems Manager command {command_id} did not " "complete successfully"),
                        command=normalize_command(command),
                        command_id=command_id,
                        command_invocations=[],
                        status=command_status,
                    )

            if (
                command_status in TERMINAL_STATUSES
                and invocations
                and all(status in TERMINAL_STATUSES for status in invocation_statuses)
            ):
                if command_status in SUCCESS_STATUSES and all(
                    status in SUCCESS_STATUSES for status in invocation_statuses
                ):
                    break

                module.fail_json(
                    changed=True,
                    msg=(f"AWS Systems Manager command {command_id} did not complete " "successfully"),
                    command=normalize_command(command),
                    command_id=command_id,
                    command_invocations=boto3_resource_list_to_ansible_dict(
                        invocations, transform_tags=False, force_tags=False
                    ),
                    status=command_status,
                )

            time.sleep(min(wait_delay, max(0, deadline - time.monotonic())))
        else:
            module.fail_json(
                changed=True,
                msg=f"Timed out waiting for AWS Systems Manager command {command_id}",
                command=normalize_command(command),
                command_id=command_id,
                command_invocations=boto3_resource_list_to_ansible_dict(
                    invocations, transform_tags=False, force_tags=False
                ),
                status=command_status,
            )

        result["command"] = normalize_command(command)
        result["command_invocations"] = boto3_resource_list_to_ansible_dict(
            invocations, transform_tags=False, force_tags=False
        )
        result["status"] = command_status

    module.exit_json(**result)


if __name__ == "__main__":
    main()
