#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: rds_subnet_group_info
version_added: "1.9.0"
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

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    scrub_none_parameters,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("rds", retry_decorator=AWSRetry.jittered_backoff())
    kwargs = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {"db_subnet_group_name": module.params["name"]},
            capitalize_first=True,
        )
    )
    try:
        subnet_groups = [
            subnet_group
            for subnet_group in paginated_query_with_retries(
                client,
                "describe_db_subnet_groups",
                **kwargs,
            ).get("DBSubnetGroups", [])
            if subnet_group.get("DBSubnetGroupName") is not None
        ]
    except is_boto3_error_code("DBSubnetGroupNotFoundFault"):
        subnet_groups = []
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to describe AWS RDS DB subnet groups",
        )

    module.exit_json(
        changed=False,
        subnet_groups=boto3_resource_list_to_ansible_dict(
            subnet_groups, transform_tags=False, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
