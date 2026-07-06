#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: rds_subnet_group_info
short_description: Gather information about aws rds subnet groups
description:
  - Gathers information about AWS Relational Database Service (RDS) DB subnet
    groups.
author:
  - Taylor Kimball
options:
  filters:
    description:
      - A dict of filters to apply when describing RDS DB subnet groups.
      - Filter names and values are passed to the RDS
        C(DescribeDBSubnetGroups) API.
    type: dict
  name:
    description:
      - RDS DB subnet group name used to limit the result set.
      - This value is passed to the RDS C(DescribeDBSubnetGroups) API
        as C(DBSubnetGroupName).
      - A subnet group that does not exist results in an empty list.
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

- name: Gather RDS subnet groups using filters
  linuxhq.aws.rds_subnet_group_info:
    filters:
      db-subnet-group-name: molecule
"""

RETURN = r"""
subnet_groups:
  description:
    - The RDS subnet groups for the current region.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("rds", retry_decorator=AWSRetry.jittered_backoff())

    filters = module.params["filters"]
    name = module.params["name"]
    request = {}
    if name:
        request["DBSubnetGroupName"] = name
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    try:
        subnet_groups = paginated_query_with_retries(
            client,
            "describe_db_subnet_groups",
            **request,
        ).get("DBSubnetGroups", [])
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
