#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_placement_group_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 placement groups
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
attributes:
  check_mode:
    description: This module only retrieves information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "group_ids": {"elements": "str", "type": "list"},
        "group_names": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    filters = module.params["filters"]
    group_ids = list(dict.fromkeys(module.params["group_ids"] or []))
    group_names = list(dict.fromkeys(module.params["group_names"] or []))

    request = {}
    if group_ids:
        request["GroupIds"] = group_ids

    if group_names:
        request["GroupNames"] = group_names

    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_placement_groups": tuple(request)},
    )

    placement_groups = query_list(
        module,
        client,
        "describe_placement_groups",
        "PlacementGroups",
        "Unable to describe EC2 placement groups",
        **request,
    )

    if any(not isinstance(placement_group, dict) for placement_group in placement_groups):
        module.fail_json(msg="EC2 returned invalid placement group information")

    module.exit_json(
        changed=False,
        placement_groups=boto3_resource_list_to_ansible_dict(placement_groups, transform_tags=True, force_tags=False),
    )


if __name__ == "__main__":
    main()
