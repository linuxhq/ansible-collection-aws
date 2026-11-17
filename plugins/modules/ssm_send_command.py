#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_send_command
version_added: '1.9.0'
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
    required: true
    type: str
  instance_ids:
    description:
      - A list of instance IDs to target directly.
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
      - Each value must be a list of strings, as the Systems Manager
        C(SendCommand) API requires.
      - Parameter values are not masked in the module's output and logs. Set
        C(no_log) on the task when a value is secret.
    default: {}
    type: dict
  targets:
    description:
      - The command targets.
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
        required: true
        type: str
      values:
        description:
          - The target values.
        elements: str
        required: true
        type: list
    type: list
  timeout_seconds:
    description:
      - The number of seconds AWS Systems Manager waits for the command to
        start running on a target. If the command has not started running on
        a target when this time is reached, it does not run there.
      - This does not limit how long a started command runs. To limit run
        time, set the document's execution timeout parameter, such as
        C(executionTimeout) for C(AWS-RunShellScript), in O(parameters).
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
      contains:
        alarms:
          description: CloudWatch alarms in the configuration.
          returned: when available
          type: list
          elements: dict
          contains:
            name:
              description: CloudWatch alarm name.
              returned: when available
              type: str
        ignore_poll_alarm_failure:
          description: Whether the command keeps running when AWS cannot retrieve the alarm status.
          returned: when available
          type: bool
    cloud_watch_output_config:
      description: CloudWatch Logs output configuration for the command.
      returned: when available
      type: dict
      contains:
        cloud_watch_log_group_name:
          description: CloudWatch Logs log group that receives the command output.
          returned: when available
          type: str
        cloud_watch_output_enabled:
          description: Whether command output is sent to CloudWatch Logs.
          returned: when available
          type: bool
    command_id:
      description: Command ID assigned by AWS Systems Manager.
      returned: when available
      type: str
    comment:
      description: Comment associated with the command.
      returned: when available
      type: str
    completed_count:
      description:
        - Number of targets whose invocation reached a terminal state, such as
          Success, Failed, Execution Timed Out, Delivery Timed Out, Cancelled,
          Terminated, or Undeliverable.
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
      description:
        - Time when the command expires. AWS then marks every invocation that
          is still Pending, In Progress, or Delayed as Delivery Timed Out.
        - It is based on the total timeout, which is O(timeout_seconds) plus
          the document's execution timeout.
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
      contains:
        notification_arn:
          description: ARN of the SNS topic that receives command status notifications.
          returned: when available
          type: str
        notification_events:
          description: Command status events that send notifications.
          returned: when available
          type: list
          elements: str
        notification_type:
          description: Notification type, C(Command) for command status changes or C(Invocation) for per-target invocation status changes.
          returned: when available
          type: str
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
        - Parameter values are returned as AWS reports them.
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
      contains:
        Key:
          description: Target key, such as C(InstanceIds) or C(tag:Name).
          returned: when available
          type: str
        Values:
          description: Target values for the key.
          returned: when available
          type: list
          elements: str
    timeout_seconds:
      description:
        - The number of seconds AWS Systems Manager waits for the command to
          start running on a target.
        - This does not limit how long a started command runs.
      returned: when available
      type: int
    triggered_alarms:
      description: Alarms triggered while the command ran.
      returned: when available
      type: list
      elements: dict
      contains:
        name:
          description: CloudWatch alarm name.
          returned: when available
          type: str
        state:
          description: State of the CloudWatch alarm, C(UNKNOWN) or C(ALARM).
          returned: when available
          type: str
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
      contains:
        cloud_watch_log_group_name:
          description: CloudWatch Logs log group that receives the command output.
          returned: when available
          type: str
        cloud_watch_output_enabled:
          description: Whether command output is sent to CloudWatch Logs.
          returned: when available
          type: bool
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
      description:
        - Fully qualified host name of the managed instance, such as
          C(ip-10-0-0-32.us-west-2.compute.internal) for an EC2 instance. It
          is not the EC2 C(Name) tag.
      returned: when available
      type: str
    notification_config:
      description: Notification configuration for the invocation.
      returned: when available
      type: dict
      contains:
        notification_arn:
          description: ARN of the SNS topic that receives command status notifications.
          returned: when available
          type: str
        notification_events:
          description: Command status events that send notifications.
          returned: when available
          type: list
          elements: str
        notification_type:
          description: Notification type, C(Command) for command status changes or C(Invocation) for per-target invocation status changes.
          returned: when available
          type: str
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    sleep_until_next_poll,
    wait_deadline,
)

SUCCESS_STATUSES = {"Success"}
TERMINAL_STATUSES = {"Cancelled", "Failed", "Success", "TimedOut"}
SEND_COMMAND_OPTIONS = [
    "comment",
    "max_concurrency",
    "max_errors",
    "timeout_seconds",
]


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


def normalize_invocations(invocations):
    return boto3_resource_list_to_ansible_dict(invocations, transform_tags=False, force_tags=False)


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
    instance_ids = list(dict.fromkeys(module.params["instance_ids"] or []))
    targets = [
        {"key": key, "values": list(values)}
        for key, values in dict.fromkeys(
            (target["key"], tuple(dict.fromkeys(target["values"]))) for target in module.params["targets"] or []
        )
    ]
    if not instance_ids and not targets:
        module.fail_json(msg="instance_ids or targets must contain at least one entry")

    require_positive_wait_bounds(module)

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    parameters = module.params["parameters"]
    wait = module.params["wait"]
    send_command_request = {option: module.params[option] for option in SEND_COMMAND_OPTIONS}
    send_command_request["document_name"] = document_name
    send_command_request["instance_ids"] = instance_ids or None
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
            msg=f"Unable to send AWS Systems Manager command using {document_name}",
        )

    command = response["Command"]
    command_id = command["CommandId"]
    command_status = command.get("Status")

    result = {
        "changed": True,
        "command": normalize_command(command),
        "command_id": command_id,
        "status": command_status,
    }

    if wait:
        deadline = wait_deadline(module)
        invocations = []

        while time.monotonic() < deadline:
            msg = f"Unable to get AWS Systems Manager command {command_id}"
            commands = query_list(module, client, "list_commands", "Commands", msg, changed=True, CommandId=command_id)
            invocations = query_list(
                module,
                client,
                "list_command_invocations",
                "CommandInvocations",
                msg,
                changed=True,
                CommandId=command_id,
                Details=True,
            )
            if not commands:
                # Run Command may not expose a newly submitted command immediately.
                sleep_until_next_poll(module, deadline)
                continue

            command = commands[0]
            command_status = command.get("Status")
            # AWS can expose an invocation before populating its status, so a missing status is polled again.
            invocation_statuses = [invocation.get("Status") for invocation in invocations]
            if command_status in TERMINAL_STATUSES and not invocations:
                if command_status in SUCCESS_STATUSES and command.get("TargetCount") == 0:
                    module.warn(
                        f"AWS Systems Manager command {command_id} completed without invocations; no targets matched"
                    )
                    break

                if command_status not in SUCCESS_STATUSES:
                    module.fail_json(
                        changed=True,
                        msg=f"AWS Systems Manager command {command_id} did not complete successfully",
                        command=normalize_command(command),
                        command_id=command_id,
                        command_invocations=[],
                        status=command_status,
                    )

            # The command and invocation APIs can become consistent at different times.
            target_count = command.get("TargetCount")
            invocation_ids = {invocation.get("InstanceId") for invocation in invocations}
            all_targets_reported = target_count is None or len(invocation_ids - {None}) >= target_count
            if (
                command_status in TERMINAL_STATUSES
                and all_targets_reported
                and invocations
                and all(status in TERMINAL_STATUSES for status in invocation_statuses)
            ):
                if command_status in SUCCESS_STATUSES and all(
                    status in SUCCESS_STATUSES for status in invocation_statuses
                ):
                    break

                module.fail_json(
                    changed=True,
                    msg=f"AWS Systems Manager command {command_id} did not complete successfully",
                    command=normalize_command(command),
                    command_id=command_id,
                    command_invocations=normalize_invocations(invocations),
                    status=command_status,
                )

            sleep_until_next_poll(module, deadline)
        else:
            module.fail_json(
                changed=True,
                msg=f"Timed out waiting for AWS Systems Manager command {command_id}",
                command=normalize_command(command),
                command_id=command_id,
                command_invocations=normalize_invocations(invocations),
                status=command_status,
            )

        result["command"] = normalize_command(command)
        result["command_invocations"] = normalize_invocations(invocations)
        result["status"] = command_status

    module.exit_json(**result)


if __name__ == "__main__":
    main()
