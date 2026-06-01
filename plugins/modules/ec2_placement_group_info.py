#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_placement_group_info
short_description: Gather information about aws placement groups
description:
  - Gathers information about EC2 placement groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 placement groups.
      - Filter names and values are passed to the EC2 C(DescribePlacementGroups) API.
    type: dict
  group_ids:
    description:
      - EC2 placement group IDs used to limit the result set.
    elements: str
    type: list
  group_names:
    description:
      - EC2 placement group names used to limit the result set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about EC2 placement groups
  linuxhq.aws.ec2_placement_group_info:

- name: Gather information about selected EC2 placement groups
  linuxhq.aws.ec2_placement_group_info:
    group_names:
      - example-placement-group

- name: Gather information about EC2 placement groups using filters
  linuxhq.aws.ec2_placement_group_info:
    filters:
      strategy: cluster
"""

RETURN = r"""
placement_groups:
  description:
    - A list of EC2 placement groups.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
)


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "group_ids": {"elements": "str", "type": "list"},
        "group_names": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())
    request = {}
    if module.params["group_ids"]:
        request["GroupIds"] = module.params["group_ids"]
    if module.params["group_names"]:
        request["GroupNames"] = module.params["group_names"]
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])

    try:
        placement_groups = client.describe_placement_groups(
            **request,
            aws_retry=True,
        ).get("PlacementGroups", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 placement groups")

    module.exit_json(
        changed=False,
        placement_groups=boto3_resource_list_to_ansible_dict(
            placement_groups, transform_tags=False, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
