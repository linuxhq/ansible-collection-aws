#!/usr/bin/python
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
region:
  description: The AWS region where the defaults were managed.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
    validated_field_differences,
)

OPTION_TO_AWS_FIELD = {
    "http_endpoint": "HttpEndpoint",
    "http_put_response_hop_limit": "HttpPutResponseHopLimit",
    "http_tokens": "HttpTokens",
    "instance_metadata_tags": "InstanceMetadataTags",
}


def build_desired_update(params):
    return scrub_none_parameters(
        {
            aws_field: params.get(option_name)
            for option_name, aws_field in OPTION_TO_AWS_FIELD.items()
        }
    )


def get_account_level(client, module):
    return aws_resource(
        client,
        module,
        "get_instance_metadata_defaults",
        "AccountLevel",
        default={},
    )


def main():
    argument_spec = {
        "http_endpoint": {
            "choices": ["disabled", "enabled", "no-preference"],
            "type": "str",
        },
        "http_put_response_hop_limit": {"type": "int"},
        "http_tokens": {
            "choices": ["optional", "required", "no-preference"],
            "type": "str",
        },
        "instance_metadata_tags": {
            "choices": ["disabled", "enabled", "no-preference"],
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_one_of=[
            [
                "http_endpoint",
                "http_put_response_hop_limit",
                "http_tokens",
                "instance_metadata_tags",
            ]
        ],
        supports_check_mode=True,
    )
    client = module.client("ec2")

    current_account_level = get_account_level(client, module)
    desired_update = build_desired_update(module.params)
    desired_account_level = aws_resource_to_snake_dict(desired_update)

    _, changed = validated_field_differences(
        module,
        current_account_level,
        desired_account_level,
        desired_account_level.keys(),
    )

    if changed and not module.check_mode:
        aws_response(
            client,
            module,
            "modify_instance_metadata_defaults",
            error_message="Unable to modify EC2 instance metadata defaults",
            **desired_update,
        )
        current_account_level = get_account_level(client, module)

    result = {
        "changed": changed,
        "account_level": aws_resource_to_snake_dict(current_account_level),
        "region": module.region,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
