#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_metadata
version_added: 1.9.1
short_description: Manage EC2 account-level instance metadata defaults
description:
  - Updates EC2 account-level instance metadata defaults for a region.
author:
  - Taylor Kimball (@tkimball83)
options:
  http_endpoint:
    description:
      - Whether the instance metadata service endpoint is enabled by default.
    choices:
      - disabled
      - enabled
      - no-preference
    type: str
  http_put_response_hop_limit:
    description:
      - The default desired HTTP PUT response hop limit.
    type: int
  http_tokens:
    description:
      - Whether IMDSv2 tokens are required by default.
    choices:
      - optional
      - required
      - no-preference
    type: str
  instance_metadata_tags:
    description:
      - Whether access to instance tags from the instance metadata service is enabled by default.
    choices:
      - disabled
      - enabled
      - no-preference
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure account-level EC2 instance metadata defaults are managed
  linuxhq.aws.ec2_instance_metadata:
    region: us-east-1
    http_endpoint: enabled
    http_put_response_hop_limit: 2
    http_tokens: required
    instance_metadata_tags: disabled
"""

RETURN = r"""
account_level:
  description:
    - The current account-level EC2 instance metadata defaults for the selected region.
  returned: always
  type: dict
proposed_account_level:
  description:
    - The account-level values that would exist after the requested update.
  returned: when a change is detected
  type: dict
region:
  description: The AWS region where the defaults were managed.
  returned: always
  type: str
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


OPTION_TO_AWS_FIELD = {
    "http_endpoint": "HttpEndpoint",
    "http_put_response_hop_limit": "HttpPutResponseHopLimit",
    "http_tokens": "HttpTokens",
    "instance_metadata_tags": "InstanceMetadataTags",
}


def get_account_level(client, module):
    try:
        response = client.get_instance_metadata_defaults()
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get EC2 instance metadata defaults")
    return response.get("AccountLevel", {})


def normalize_account_level(account_level):
    return camel_dict_to_snake_dict(account_level)


def build_desired_update(params):
    desired = {}
    for option_name, aws_field in OPTION_TO_AWS_FIELD.items():
        value = params.get(option_name)
        if value is not None:
            desired[aws_field] = value
    return desired


def main() -> None:
    argument_spec = {
        "http_endpoint": {"choices": ["disabled", "enabled", "no-preference"], "type": "str"},
        "http_put_response_hop_limit": {"type": "int"},
        "http_tokens": {"choices": ["optional", "required", "no-preference"], "type": "str"},
        "instance_metadata_tags": {"choices": ["disabled", "enabled", "no-preference"], "type": "str"},
        "validate_certs": {"default": True, "type": "bool"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_one_of=[["http_endpoint", "http_put_response_hop_limit", "http_tokens", "instance_metadata_tags"]],
        supports_check_mode=True,
    )
    client = module.client("ec2")

    current_account_level = get_account_level(client, module)
    desired_update = build_desired_update(module.params)
    proposed_account_level = dict(current_account_level)
    proposed_account_level.update(desired_update)

    changed = any(
        current_account_level.get(aws_field) != desired_value
        for aws_field, desired_value in desired_update.items()
    )

    if changed and not module.check_mode:
        try:
            client.modify_instance_metadata_defaults(**desired_update)
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to modify EC2 instance metadata defaults")
        current_account_level = get_account_level(client, module)
        proposed_account_level = current_account_level

    result = {
        "changed": changed,
        "account_level": normalize_account_level(current_account_level),
        "region": module.region,
    }

    if changed:
        result["proposed_account_level"] = normalize_account_level(proposed_account_level)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
