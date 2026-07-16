#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_logging
short_description: Manage aws wafv2 web acls
description:
  - Manages AWS WAFv2 web ACL logging configuration.
  - Supports enabling, updating, and removing logging for a web ACL.
  - Updates replace the logging configuration; fields not managed by this
    module, such as redacted fields and logging filters, are removed by the
    AWS C(PutLoggingConfiguration) API.
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
      - CloudFront web ACLs require the C(us-east-1) region.
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
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
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
    state = module.params["state"]

    if state == "present" and not module.params["log_destination_configs"]:
        module.fail_json(
            msg="log_destination_configs must contain at least 1 destination ARN"
        )

    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())
    methods = {"get_logging_configuration": ("ResourceArn",)}
    if state == "present":
        methods["put_logging_configuration"] = ("LoggingConfiguration",)
    if state == "absent":
        methods["delete_logging_configuration"] = ("ResourceArn",)

    require_client_methods(module, client, "WAFv2", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
