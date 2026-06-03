#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_send_command
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
      - The command targets.
      - Target keys may be provided in snake_case or AWS native PascalCase.
      - Each target requires a target key and values.
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
      - key: instanceids
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
status:
  description:
    - The aggregate command status.
  returned: when not in check mode
  type: str
"""

import time

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
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
SEND_COMMAND_OPTIONS = [
    "comment",
    "instance_ids",
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
        required_one_of=[["instance_ids", "targets"]],
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    document_name = module.params["document_name"]
    parameters = module.params["parameters"]
    targets = module.params["targets"]
    wait = module.params["wait"]
    send_command_request = {
        option: module.params[option] for option in SEND_COMMAND_OPTIONS
    }
    send_command_request["document_name"] = document_name
    send_command_request["parameters"] = parameters
    if targets is not None:
        send_command_request["targets"] = [
            snake_dict_to_camel_dict(target, capitalize_first=True)
            for target in targets
        ]
    send_command_args = scrub_none_parameters(
        snake_dict_to_camel_dict(send_command_request, capitalize_first=True)
    )
    send_command_args["Parameters"] = parameters

    method_names = {"send_command"}
    if wait:
        method_names.update({"list_commands", "list_command_invocations"})

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=(
                    "Installed botocore does not support Systems Manager "
                    f"{method_name}"
                )
            )

    required_method_parameters = {
        "send_command": set(send_command_args),
        "list_commands": {"CommandId"},
        "list_command_invocations": {"CommandId", "Details"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Systems Manager "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if module.check_mode:
        module.exit_json(changed=True)

    try:
        command = client.send_command(**send_command_args, aws_retry=True).get(
            "Command", {}
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to send AWS Systems Manager command using " f"{document_name}"
            ),
        )

    result = {
        "changed": True,
        "command": normalize_command(command),
        "command_id": command.get("CommandId"),
        "status": command.get("Status"),
    }

    if wait:
        command_id = command.get("CommandId")
        wait_delay = max(1, module.params["wait_delay"])
        deadline = time.monotonic() + module.params["wait_timeout"]

        while time.monotonic() < deadline:
            try:
                commands = paginated_query_with_retries(
                    client,
                    "list_commands",
                    CommandId=command_id,
                ).get("Commands", [])
                invocations = paginated_query_with_retries(
                    client,
                    "list_command_invocations",
                    CommandId=command_id,
                    Details=True,
                ).get("CommandInvocations", [])
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to get AWS Systems Manager command {command_id}",
                )

            if not commands:
                module.fail_json(
                    msg=(
                        f"AWS Systems Manager command {command_id} was not returned "
                        "by list_commands"
                    ),
                )

            command = commands[0]
            statuses = set()
            for invocation in invocations:
                invocation_status = invocation.get("Status")
                if invocation_status:
                    statuses.add(invocation_status)

            command_status = command.get("Status")

            if command_status in TERMINAL_STATUSES and not invocations:
                if command_status in SUCCESS_STATUSES:
                    break

                module.fail_json(
                    msg=(
                        f"AWS Systems Manager command {command_id} did not complete "
                        "successfully"
                    ),
                    command=normalize_command(command),
                    command_id=command_id,
                    command_invocations=[],
                    status=command_status,
                )

            if invocations and statuses and statuses.issubset(TERMINAL_STATUSES):
                if statuses.issubset(SUCCESS_STATUSES):
                    break

                module.fail_json(
                    msg=(
                        f"AWS Systems Manager command {command_id} did not complete "
                        "successfully"
                    ),
                    command=normalize_command(command),
                    command_id=command_id,
                    command_invocations=boto3_resource_list_to_ansible_dict(
                        invocations, transform_tags=False, force_tags=False
                    ),
                    status=command_status,
                )

            time.sleep(wait_delay)
        else:
            module.fail_json(
                msg=f"Timed out waiting for AWS Systems Manager command {command_id}",
                command_id=command_id,
            )

        result["command"] = normalize_command(command)
        result["command_invocations"] = boto3_resource_list_to_ansible_dict(
            invocations, transform_tags=False, force_tags=False
        )
        result["status"] = command.get("Status")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
