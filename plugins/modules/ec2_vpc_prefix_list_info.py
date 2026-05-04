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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def get_prefix_list_entries(client, module, prefix_list_id):
    entries = []
    next_token = None

    try:
        while True:
            request = {"PrefixListId": prefix_list_id}
            if next_token:
                request["NextToken"] = next_token

            response = client.get_managed_prefix_list_entries(**request)
            entries.extend(response.get("Entries", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 VPC managed prefix list entries for {prefix_list_id}",
        )

    return entries


def main():
    module = AnsibleAWSModule(
        argument_spec={"name": {"type": "str"}},
        supports_check_mode=True,
    )
    client = module.client("ec2")

    prefix_lists = []
    next_token = None

    try:
        while True:
            request = {}
            if next_token:
                request["NextToken"] = next_token

            response = client.describe_managed_prefix_lists(**request)
            prefix_lists.extend(response.get("PrefixLists", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 VPC managed prefix lists")

    module.exit_json(
        changed=False,
        prefix_lists=[
            camel_dict_to_snake_dict(prefix_list)
            | {
                "entries": get_prefix_list_entries(
                    client, module, prefix_list["PrefixListId"]
                )
            }
            for prefix_list in prefix_lists
            if prefix_list.get("PrefixListName")
            and (
                module.params["name"] is None
                or prefix_list.get("PrefixListName") == module.params["name"]
            )
        ],
    )


if __name__ == "__main__":
    main()
