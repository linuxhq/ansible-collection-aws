#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_logging
version_added: 1.9.1
short_description: Manage AWS WAFv2 web ACL logging configuration
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
    elements: str
    type: list
  logging_filter:
    description:
      - Optional AWS WAF logging filter configuration.
    type: dict
  redacted_fields:
    description:
      - Optional fields to redact from the emitted logs.
    elements: dict
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
proposed_logging_configuration:
  description:
    - The logging configuration that would be applied.
  returned: when a change is detected and state is present
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

import json

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return (
        getattr(error, "response", {}).get("Error", {}).get("Code")
        == "WAFNonexistentItemException"
    )


def canonicalize(value):
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        items = [canonicalize(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def get_logging_configuration(client, module, resource_arn):
    try:
        response = client.get_logging_configuration(ResourceArn=resource_arn)
    except Exception as e:
        if is_not_found_error(e):
            return None
        module.fail_json_aws(
            e, msg=f"Unable to get AWS WAFv2 logging configuration for {resource_arn}"
        )

    return response.get("LoggingConfiguration")


def build_desired_configuration(module):
    desired = {
        "ResourceArn": module.params["resource_arn"],
        "LogDestinationConfigs": module.params["log_destination_configs"],
    }

    if module.params["logging_filter"] is not None:
        desired["LoggingFilter"] = module.params["logging_filter"]
    if module.params["redacted_fields"] is not None:
        desired["RedactedFields"] = module.params["redacted_fields"]

    return desired


def ensure_present(client, module):
    current = get_logging_configuration(client, module, module.params["resource_arn"])
    desired = build_desired_configuration(module)

    comparable_current = None
    if current is not None:
        comparable_current = {
            key: value
            for key, value in current.items()
            if key
            in (
                "LogDestinationConfigs",
                "LoggingFilter",
                "RedactedFields",
                "ResourceArn",
            )
        }

    changed = canonicalize(comparable_current) != canonicalize(desired)

    if changed and not module.check_mode:
        try:
            client.put_logging_configuration(LoggingConfiguration=desired)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to manage AWS WAFv2 logging configuration for {module.params['resource_arn']}",
            )
        current = get_logging_configuration(
            client, module, module.params["resource_arn"]
        )
    elif changed and module.check_mode:
        current = desired

    result = {
        "changed": changed,
        "resource_arn": module.params["resource_arn"],
        "state": "present",
        "logging_configuration": camel_dict_to_snake_dict(current or desired),
    }

    if changed:
        result["proposed_logging_configuration"] = camel_dict_to_snake_dict(desired)

    module.exit_json(**result)


def ensure_absent(client, module):
    current = get_logging_configuration(client, module, module.params["resource_arn"])
    changed = current is not None

    if changed and not module.check_mode:
        try:
            client.delete_logging_configuration(
                ResourceArn=module.params["resource_arn"]
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS WAFv2 logging configuration for {module.params['resource_arn']}",
            )

    module.exit_json(
        changed=changed,
        resource_arn=module.params["resource_arn"],
        state="absent",
    )


def main():
    argument_spec = {
        "log_destination_configs": {"elements": "str", "type": "list"},
        "logging_filter": {"type": "dict"},
        "redacted_fields": {"elements": "dict", "type": "list"},
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
    client = module.client("wafv2")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
