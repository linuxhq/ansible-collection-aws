#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_logging
short_description: Manage AWS WAFv2 web ACL logging
description:
  - Manages AWS WAFv2 web ACL logging configuration.
  - Supports enabling, updating, and removing logging for a web ACL.
  - Updates preserve logging configuration fields not managed by this module,
    such as redacted fields and logging filters.
author:
  - Taylor Kimball (@tkimball83)
options:
  log_destination_configs:
    description:
      - The logging destination ARNs for the web ACL.
      - AWS WAF allows one destination per web ACL.
      - Entries must not be empty.
      - This is required when O(state=present).
    elements: str
    type: list
  resource_arn:
    description:
      - The ARN of the WAFv2 web ACL to manage logging for.
      - This must not be empty.
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
attributes:
  check_mode:
    description: The module reports the logging configuration that would result from the requested changes.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
  contains:
    log_destination_configs:
      description: The logging destination ARNs.
      returned: always
      type: list
      elements: str
    log_scope:
      description: The scope of the logging configuration.
      returned: when available
      type: str
    log_type:
      description: The type of the logging configuration.
      returned: when available
      type: str
    logging_filter:
      description: The logging filter configuration.
      returned: when available
      type: dict
    managed_by_firewall_manager:
      description: Whether AWS Firewall Manager manages the configuration.
      returned: when available
      type: bool
    redacted_fields:
      description: The request fields redacted from the logs.
      returned: when available
      type: list
      elements: dict
    resource_arn:
      description: The ARN of the AWS WAFv2 web ACL.
      returned: always
      type: str
resource_arn:
  description: The ARN of the managed WAFv2 web ACL.
  returned: always
  type: str
state:
  description: The requested state of the logging configuration.
  returned: always
  type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
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
        except is_boto3_error_code("WAFNonexistentItemException"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to delete AWS WAFv2 logging configuration for " f"{resource_arn}"),
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
        normalized_current = boto3_resource_to_ansible_dict(current, transform_tags=False, force_tags=False)
        current_comparable = {
            "log_destination_configs": normalized_current.get("log_destination_configs") or [],
            "resource_arn": normalized_current.get("resource_arn"),
        }

    desired_comparable = {
        "log_destination_configs": log_destination_configs,
        "resource_arn": resource_arn,
    }
    desired = {
        key: current[key]
        for key in ("LoggingFilter", "LogScope", "LogType", "RedactedFields")
        if current and key in current
    }
    desired.update(
        {
            "LogDestinationConfigs": log_destination_configs,
            "ResourceArn": resource_arn,
        }
    )
    changed = (current_comparable or {}) != desired_comparable

    if changed and not module.check_mode:
        try:
            response = client.put_logging_configuration(
                LoggingConfiguration=desired,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to manage AWS WAFv2 logging configuration for " f"{resource_arn}"),
            )

        current = response.get("LoggingConfiguration") if isinstance(response, dict) else None
        if not isinstance(current, dict) or not current:
            module.fail_json(
                changed=True,
                msg=("AWS WAFv2 did not return the logging configuration for " f"{resource_arn}"),
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
        response = client.get_logging_configuration(
            ResourceArn=resource_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("WAFNonexistentItemException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS WAFv2 logging configuration for {resource_arn}",
        )

    if not isinstance(response, dict):
        module.fail_json(msg=f"AWS WAFv2 returned an unexpected logging configuration response for {resource_arn}")

    current = response.get("LoggingConfiguration")
    if current is not None and not isinstance(current, dict):
        module.fail_json(msg=f"AWS WAFv2 returned an unexpected logging configuration response for {resource_arn}")

    return current


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
    resource_arn = module.params["resource_arn"]

    if not resource_arn:
        module.fail_json(msg="resource_arn must not be empty")

    if state == "present" and len(module.params["log_destination_configs"] or []) != 1:
        module.fail_json(msg="log_destination_configs must contain exactly 1 ARN")

    if state == "present" and not module.params["log_destination_configs"][0]:
        module.fail_json(msg="log_destination_configs must not contain empty entries")

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
