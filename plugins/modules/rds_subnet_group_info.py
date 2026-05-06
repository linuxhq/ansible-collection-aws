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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_request_params,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
)


def list_subnet_groups(client, module):
    kwargs = aws_request_params({"db_subnet_group_name": module.params["name"]})

    subnet_groups = [
        subnet_group
        for subnet_group in aws_paginated_list(
            client,
            module,
            "describe_db_subnet_groups",
            "DBSubnetGroups",
            ignore_error_codes=(
                "DBSubnetGroupNotFoundFault"
                if module.params["name"] is not None
                else None
            ),
            ignored_error_result=[],
            **kwargs,
        )
        if subnet_group.get("DBSubnetGroupName") is not None
    ]
    return aws_resource_list_to_snake_dicts(subnet_groups)


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
