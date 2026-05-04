#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_placement_group_info
version_added: 1.9.1
short_description: Gather information about EC2 placement groups
description:
  - Gathers information about EC2 placement groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - Optional placement group name used to limit the result set.
    type: str
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
    name: example-placement-group
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
    boto3_resource_list_to_ansible_dict,
    scrub_none_parameters,
)


def main():
    argument_spec = {
        "name": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ec2")

    request = scrub_none_parameters(
        {"GroupNames": [module.params["name"]] if module.params["name"] else None}
    )

    describe_placement_groups = AWSRetry.jittered_backoff()(
        client.describe_placement_groups
    )
    try:
        response = describe_placement_groups(**request)
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 placement groups")

    module.exit_json(
        changed=False,
        placement_groups=boto3_resource_list_to_ansible_dict(
            response.get("PlacementGroups", []),
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
