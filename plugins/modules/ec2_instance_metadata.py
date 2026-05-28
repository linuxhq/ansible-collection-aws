#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_metadata
short_description: Manage aws ec2 instance metadata defaults
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

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

MANAGED_OPTIONS = [
    "http_endpoint",
    "http_put_response_hop_limit",
    "http_tokens",
    "instance_metadata_tags",
]


def get_instance_metadata_defaults(client, module):
    try:
        return boto3_resource_to_ansible_dict(
            client.get_instance_metadata_defaults(aws_retry=True).get(
                "AccountLevel", {}
            ),
            transform_tags=False,
            force_tags=False,
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get EC2 instance metadata defaults")


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
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    current_account_level = get_instance_metadata_defaults(client, module)
    desired_update = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                option_name: module.params[option_name]
                for option_name in MANAGED_OPTIONS
            },
            capitalize_first=True,
        )
    )
    desired_fields = [
        option_name
        for option_name in MANAGED_OPTIONS
        if module.params[option_name] is not None
    ]

    desired = {
        option_name: module.params[option_name] for option_name in desired_fields
    }
    current = {field: current_account_level.get(field) for field in desired_fields}
    changed = current != desired

    if changed and not module.check_mode:
        try:
            client.modify_instance_metadata_defaults(**desired_update, aws_retry=True)
        except Exception as e:
            module.fail_json_aws(
                e, msg="Unable to modify EC2 instance metadata defaults"
            )
        current_account_level = get_instance_metadata_defaults(client, module)
    elif changed and module.check_mode:
        current_account_level = dict(current_account_level)
        current_account_level.update(desired)

    result = {
        "changed": changed,
        "account_level": current_account_level,
        "region": module.region,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
