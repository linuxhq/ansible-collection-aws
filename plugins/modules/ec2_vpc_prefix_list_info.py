#!/usr/bin/python

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_prefix_list_info
version_added: 1.9.1
short_description: Gather information about EC2 VPC prefix lists
description:
  - Gathers information about EC2 VPC managed prefix lists.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - Optional managed prefix list name used to limit the result set.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about EC2 VPC prefix lists
  linuxhq.aws.ec2_vpc_prefix_list_info:

- name: Gather information about a selected EC2 VPC prefix list
  linuxhq.aws.ec2_vpc_prefix_list_info:
    name: molecule-localhost
"""

RETURN = r"""
prefix_lists:
  description:
    - A list of EC2 VPC managed prefix lists, including their entries.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.ec2 import (
    describe_managed_prefix_lists,
    get_managed_prefix_list_entries,
    normalize_managed_prefix_list,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={"name": {"type": "str"}},
        supports_check_mode=True,
    )
    client = module.client("ec2")
    name = module.params["name"]
    prefix_lists = []
    for prefix_list in describe_managed_prefix_lists(client, module, name):
        prefix_list_name = prefix_list.get("PrefixListName")
        if prefix_list_name and (name is None or prefix_list_name == name):
            prefix_lists.append(prefix_list)

    module.exit_json(
        changed=False,
        prefix_lists=[
            normalize_managed_prefix_list(
                prefix_list,
                get_managed_prefix_list_entries(
                    client, module, prefix_list["PrefixListId"]
                ),
            )
            for prefix_list in prefix_lists
        ],
    )


if __name__ == "__main__":
    main()
