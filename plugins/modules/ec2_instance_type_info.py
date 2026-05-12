#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_instance_type_info
short_description: Gather information about aws instance types
description:
  - Gathers information about EC2 instance types.
  - This module maps to the EC2 C(DescribeInstanceTypes) API, the API behind
    C(aws ec2 describe-instance-types).
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 instance types.
      - Filter names and values are passed to the EC2
        C(DescribeInstanceTypes) API.
    type: dict
  instance_types:
    description:
      - EC2 instance type names used to limit the result set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about all EC2 instance types
  linuxhq.aws.ec2_instance_type_info:

- name: Gather information about selected EC2 instance types
  linuxhq.aws.ec2_instance_type_info:
    instance_types:
      - t3.micro
      - m7i.large

- name: Gather information about current generation x86_64 instance types
  linuxhq.aws.ec2_instance_type_info:
    filters:
      current-generation: true
      processor-info.supported-architecture:
        - x86_64

- name: Gather information about burstable instance types
  linuxhq.aws.ec2_instance_type_info:
    filters:
      burstable-performance-supported: true
      instance-type:
        - t3.*
        - t4g.*
"""

RETURN = r"""
instance_types:
  description:
    - A list of EC2 instance type information.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    scrub_none_parameters,
)


def build_request(module):
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {"instance_types": module.params["instance_types"] or None},
            capitalize_first=True,
        )
    )
    filters = module.params["filters"] or {}
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)
    return request


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "instance_types": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    try:
        instance_types = paginated_query_with_retries(
            client,
            "describe_instance_types",
            **build_request(module),
        ).get("InstanceTypes", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 instance types")

    module.exit_json(
        changed=False,
        instance_types=boto3_resource_list_to_ansible_dict(
            instance_types, transform_tags=False, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
