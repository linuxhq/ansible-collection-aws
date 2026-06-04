#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_logging
short_description: Manage aws wafv2 web acls
description:
  - Manages AWS WAFv2 web ACL logging configuration.
  - Supports enabling, updating, and removing logging for a web ACL.
author:
  - Taylor Kimball (@tkimball83)
options:
  log_destination_configs:
    description:
      - The logging destination ARNs for the web ACL.
      - AWS WAF allows one destination per web ACL.
      - This is required when O(state=present).
    elements: str
    type: list
  resource_arn:
    description:
      - The ARN of the WAFv2 web ACL to manage logging for.
    required: true
    type: str
  state:
    description:
      - Whether the logging configuration should exist.
    choices:
      - absent
      - present
    default: present
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure WAFv2 web ACL logging is enabled
  linuxhq.aws.wafv2_web_acl_logging:
    resource_arn: arn:aws:wafv2:us-east-1:123456789012:regional/webacl/example/12345678-1234-1234-1234-123456789012
    log_destination_configs:
      - arn:aws:logs:us-east-1:123456789012:log-group:aws-waf-logs-example:*

- name: Ensure WAFv2 web ACL logging is absent
  linuxhq.aws.wafv2_web_acl_logging:
    resource_arn: arn:aws:wafv2:us-east-1:123456789012:regional/webacl/example/12345678-1234-1234-1234-123456789012
    state: absent
"""

RETURN = r"""
logging_configuration:
  description:
    - The current AWS WAFv2 logging configuration after module execution.
  returned: when state is present
  type: dict
resource_arn:
  description: The ARN of the managed WAFv2 web ACL.
  returned: always
  type: str
state:
  description: The requested state of the logging configuration.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def ensure_absent(client, module):
    current = get_logging_configuration(client, module)
    resource_arn = module.params["resource_arn"]
    changed = current is not None

    if changed and not module.check_mode:
        try:
            client.delete_logging_configuration(
                ResourceArn=resource_arn,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to delete AWS WAFv2 logging configuration for "
                    f"{resource_arn}"
                ),
            )

    module.exit_json(
        changed=changed,
        resource_arn=resource_arn,
        state="absent",
    )


def ensure_present(client, module):
    log_destination_configs = module.params["log_destination_configs"]
    resource_arn = module.params["resource_arn"]
    current = get_logging_configuration(client, module)
    current_comparable = None
    if current:
        normalized_current = boto3_resource_to_ansible_dict(
            current, transform_tags=False, force_tags=False
        )
        current_comparable = {
            "log_destination_configs": normalized_current.get(
                "log_destination_configs"
            ),
            "resource_arn": normalized_current.get("resource_arn"),
        }
    desired_comparable = {
        "log_destination_configs": log_destination_configs,
        "resource_arn": resource_arn,
    }
    desired = {
        "LogDestinationConfigs": log_destination_configs,
        "ResourceArn": resource_arn,
    }
    changed = (current_comparable or {}) != desired_comparable

    if changed and not module.check_mode:
        try:
            current = client.put_logging_configuration(
                LoggingConfiguration=desired,
                aws_retry=True,
            ).get("LoggingConfiguration")
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to manage AWS WAFv2 logging configuration for "
                    f"{resource_arn}"
                ),
            )

    elif changed and module.check_mode:
        current = desired

    result = {
        "changed": changed,
        "resource_arn": resource_arn,
        "state": "present",
        "logging_configuration": boto3_resource_to_ansible_dict(
            current or desired, transform_tags=False, force_tags=False
        ),
    }

    module.exit_json(**result)


def get_logging_configuration(client, module):
    resource_arn = module.params["resource_arn"]

    try:
        return client.get_logging_configuration(
            ResourceArn=resource_arn,
            aws_retry=True,
        ).get("LoggingConfiguration")
    except is_boto3_error_code("WAFNonexistentItemException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS WAFv2 logging configuration for {resource_arn}",
        )


def main():
    argument_spec = {
        "log_destination_configs": {"elements": "str", "type": "list"},
        "resource_arn": {"required": True, "type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["log_destination_configs"])],
        supports_check_mode=True,
    )
    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    method_names = {"get_logging_configuration"}
    if state == "present":
        method_names.add("put_logging_configuration")
    elif state == "absent":
        method_names.add("delete_logging_configuration")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support WAFv2 {method_name}"
            )

    required_method_parameters = {
        "delete_logging_configuration": {"ResourceArn"},
        "get_logging_configuration": {"ResourceArn"},
        "put_logging_configuration": {"LoggingConfiguration"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support WAFv2 "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
