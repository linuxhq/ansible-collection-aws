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
  returned: always
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
proposed_command:
  description:
    - The command request that would be sent.
  returned: always
  type: dict
status:
  description:
    - The aggregate command status.
  returned: when not in check mode
  type: str
"""

import time

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule

TERMINAL_STATUSES = {"Cancelled", "Cancelling", "Failed", "Success", "TimedOut"}
SUCCESS_STATUSES = {"Success"}


def snake_top_level_dict(value):
    return {
        camel_dict_to_snake_dict({key: None}).popitem()[0]: item
        for key, item in value.items()
    }


def build_send_command_args(module):
    args = {
        "DocumentName": module.params["document_name"],
        "Parameters": module.params["parameters"],
    }

    for module_key, aws_key in (
        ("comment", "Comment"),
        ("instance_ids", "InstanceIds"),
        ("max_concurrency", "MaxConcurrency"),
        ("max_errors", "MaxErrors"),
        ("targets", "Targets"),
        ("timeout_seconds", "TimeoutSeconds"),
    ):
        value = module.params.get(module_key)
        if value is not None:
            args[aws_key] = value

    return args


def list_command_invocations(client, module, command_id):
    invocations = []
    next_token = None

    while True:
        kwargs = {
            "CommandId": command_id,
            "Details": True,
        }
        if next_token:
            kwargs["NextToken"] = next_token

        try:
            response = client.list_command_invocations(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list AWS Systems Manager command invocations for {command_id}",
            )

        invocations.extend(response.get("CommandInvocations", []))
        next_token = response.get("NextToken")
        if not next_token:
            break

    return invocations


def get_command(client, module, command_id):
    try:
        response = client.list_commands(CommandId=command_id)
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
                command=snake_top_level_dict(command),
                command_id=command_id,
                command_invocations=[],
                status=command.get("Status"),
            )

        if invocations and statuses and statuses.issubset(TERMINAL_STATUSES):
            if statuses.issubset(SUCCESS_STATUSES):
                return command, invocations

            module.fail_json(
                msg=f"AWS Systems Manager command {command_id} did not complete successfully",
                command=snake_top_level_dict(command),
                command_id=command_id,
                command_invocations=[
                    camel_dict_to_snake_dict(invocation) for invocation in invocations
                ],
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
    proposed_command = build_send_command_args(module)

    if module.check_mode:
        module.exit_json(
            changed=True,
            proposed_command=snake_top_level_dict(proposed_command),
        )

    try:
        response = client.send_command(**proposed_command)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to send AWS Systems Manager command using {module.params['document_name']}",
        )

    command = response.get("Command", {})
    result = {
        "changed": True,
        "command": snake_top_level_dict(command),
        "command_id": command.get("CommandId"),
        "proposed_command": snake_top_level_dict(proposed_command),
        "status": command.get("Status"),
    }

    if module.params["wait"]:
        command, invocations = wait_for_command(
            client, module, command.get("CommandId")
        )
        result["command"] = snake_top_level_dict(command)
        result["command_invocations"] = [
            camel_dict_to_snake_dict(invocation) for invocation in invocations
        ]
        result["status"] = command.get("Status")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
