#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: rds_subnet_group_info
version_added: 1.9.1
short_description: Gather AWS RDS subnet group information
description:
  - Gathers AWS Relational Database Service subnet groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The RDS subnet group name to query.
      - When omitted, all subnet groups are returned.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather RDS subnet group information
  linuxhq.aws.rds_subnet_group_info:

- name: Gather a specific RDS subnet group
  linuxhq.aws.rds_subnet_group_info:
    name: molecule
"""

RETURN = r"""
subnet_groups:
  description:
    - The RDS subnet groups for the current region.
  returned: always
  type: list
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_subnet_groups(client, module):
    subnet_groups = []
    marker = None

    while True:
        kwargs = {}
        if module.params["name"] is not None:
            kwargs["DBSubnetGroupName"] = module.params["name"]
        if marker:
            kwargs["Marker"] = marker

        try:
            response = client.describe_db_subnet_groups(**kwargs)
        except Exception as e:
            if (
                module.params["name"] is not None
                and getattr(e, "response", {}).get("Error", {}).get("Code")
                == "DBSubnetGroupNotFoundFault"
            ):
                return []
            module.fail_json_aws(
                e,
                msg="Unable to describe AWS RDS subnet groups",
            )

        subnet_groups.extend(response.get("DBSubnetGroups", []))
        marker = response.get("Marker")
        if not marker:
            break

    return [
        camel_dict_to_snake_dict(subnet_group)
        for subnet_group in subnet_groups
        if subnet_group.get("DBSubnetGroupName") is not None
    ]


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("rds")

    module.exit_json(
        changed=False,
        subnet_groups=list_subnet_groups(client, module),
    )


if __name__ == "__main__":
    main()
