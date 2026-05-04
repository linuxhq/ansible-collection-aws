#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_send_command
version_added: 1.9.1
short_description: Send AWS Systems Manager commands
description:
  - Sends an AWS Systems Manager Run Command request.
  - Optionally waits for command invocations to complete.
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
      - The command targets in AWS format.
      - Preserve AWS target keys such as C(Key) and C(Values).
    elements: dict
    type: list
  timeout_seconds:
    description:
      - The timeout in seconds for the command execution.
    type: int
  wait:
    description:
      - Whether to wait for command invocations to complete.
    default: false
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
    default: 600
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a shell command is executed
  linuxhq.aws.ssm_send_command:
    document_name: AWS-RunShellScript
    parameters:
      commands:
        - touch /tmp/molecule
    targets:
      - Key: instanceids
        Values:
          - i-0123456789abcdef0
    wait: true
"""

RETURN = r"""
command:
  description:
    - The command metadata returned by AWS Systems Manager.
  returned: when not in check mode
  type: dict
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
status:
  description:
    - The aggregate command status.
  returned: when not in check mode
  type: str
"""

import time
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

SUCCESS_STATUSES = {"Success"}
TERMINAL_STATUSES = {"Cancelled", "Cancelling", "Failed", "Success", "TimedOut"}


def build_send_command_args(params):
    return scrub_none_parameters(
        {
            "Comment": params["comment"],
            "DocumentName": params["document_name"],
            "InstanceIds": params["instance_ids"],
            "MaxConcurrency": params["max_concurrency"],
            "MaxErrors": params["max_errors"],
            "Parameters": params["parameters"],
            "Targets": params["targets"],
            "TimeoutSeconds": params["timeout_seconds"],
        }
    )


def get_command(client, module, command_id):
    list_commands = AWSRetry.jittered_backoff()(client.list_commands)
    try:
        response = list_commands(CommandId=command_id)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Systems Manager command {command_id}",
        )

    commands = response.get("Commands", [])
    if not commands:
        module.fail_json(
            msg=f"AWS Systems Manager command {command_id} was not returned by list_commands",
        )

    return commands[0]


def list_command_invocations(client, module, command_id):
    try:
        response = paginated_query_with_retries(
            client,
            "list_command_invocations",
            CommandId=command_id,
            Details=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list AWS Systems Manager command invocations for {command_id}",
        )
    return response.get("CommandInvocations", [])


def normalize_command(command):
    return boto3_resource_to_ansible_dict(
        command,
        force_tags=False,
        ignore_list=["Parameters", "Targets"],
    )


def normalize_command_invocations(invocations):
    return boto3_resource_list_to_ansible_dict(
        invocations,
        force_tags=False,
    )


def wait_for_command(client, module, command_id):
    deadline = time.time() + module.params["wait_timeout"]

    while time.time() < deadline:
        command = get_command(client, module, command_id)
        invocations = list_command_invocations(client, module, command_id)
        statuses = {
            invocation.get("Status")
            for invocation in invocations
            if invocation.get("Status")
        }

        if command.get("Status") in TERMINAL_STATUSES and not invocations:
            if command.get("Status") in SUCCESS_STATUSES:
                return command, invocations

            module.fail_json(
                msg=f"AWS Systems Manager command {command_id} did not complete successfully",
                command=normalize_command(command),
                command_id=command_id,
                command_invocations=[],
                status=command.get("Status"),
            )

        if invocations and statuses and statuses.issubset(TERMINAL_STATUSES):
            if statuses.issubset(SUCCESS_STATUSES):
                return command, invocations

            module.fail_json(
                msg=f"AWS Systems Manager command {command_id} did not complete successfully",
                command=normalize_command(command),
                command_id=command_id,
                command_invocations=normalize_command_invocations(invocations),
                status=command.get("Status"),
            )

        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=f"Timed out waiting for AWS Systems Manager command {command_id}",
        command_id=command_id,
    )


def main():
    argument_spec = {
        "comment": {"type": "str"},
        "document_name": {"required": True, "type": "str"},
        "instance_ids": {"elements": "str", "type": "list"},
        "max_concurrency": {"type": "str"},
        "max_errors": {"type": "str"},
        "parameters": {"default": {}, "type": "dict"},
        "targets": {"elements": "dict", "type": "list"},
        "timeout_seconds": {"type": "int"},
        "wait": {"default": False, "type": "bool"},
        "wait_delay": {"default": 5, "type": "int"},
        "wait_timeout": {"default": 600, "type": "int"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_one_of=[["instance_ids", "targets"]],
        supports_check_mode=True,
    )
    client = module.client("ssm")
    send_command_args = build_send_command_args(module.params)

    if module.check_mode:
        module.exit_json(changed=True)

    send_command = AWSRetry.jittered_backoff()(client.send_command)
    try:
        response = send_command(**send_command_args)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to send AWS Systems Manager command using {module.params['document_name']}",
        )

    command = response.get("Command", {})
    result = {
        "changed": True,
        "command": normalize_command(command),
        "command_id": command.get("CommandId"),
        "status": command.get("Status"),
    }

    if module.params["wait"]:
        command, invocations = wait_for_command(
            client, module, command.get("CommandId")
        )
        result["command"] = normalize_command(command)
        result["command_invocations"] = normalize_command_invocations(invocations)
        result["status"] = command.get("Status")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
