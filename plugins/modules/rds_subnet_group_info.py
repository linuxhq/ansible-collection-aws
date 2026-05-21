#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: rds_subnet_group_info
short_description: Gather information about aws rds subnet groups
description:
  - Gathers AWS Relational Database Service subnet groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing RDS DB subnet groups.
      - Filter names and values are passed to the RDS
        C(DescribeDBSubnetGroups) API.
    type: dict
  names:
    description:
      - RDS DB subnet group names used to limit the result set.
    elements: str
    type: list
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
    names:
      - molecule

- name: Gather RDS subnet groups using filters
  linuxhq.aws.rds_subnet_group_info:
    filters:
      vpc-id: vpc-0123456789abcdef0
"""

RETURN = r"""
subnet_groups:
  description:
    - The RDS subnet groups for the current region.
  returned: always
  type: list
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


def build_request(module, name=None):
    request = {}
    if name:
        request["DBSubnetGroupName"] = name
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])
    return request


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "names": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )
    client = module.client("rds", retry_decorator=AWSRetry.jittered_backoff())
    try:
        subnet_groups = []
        if module.params["names"]:
            for name in module.params["names"]:
                try:
                    subnet_groups.extend(
                        client.describe_db_subnet_groups(
                            **build_request(module, name),
                            aws_retry=True,
                        ).get("DBSubnetGroups", [])
                    )
                except is_boto3_error_code("DBSubnetGroupNotFoundFault"):
                    continue
        else:
            subnet_groups = paginated_query_with_retries(
                client,
                "describe_db_subnet_groups",
                **build_request(module),
            ).get("DBSubnetGroups", [])
        subnet_groups = [
            subnet_group
            for subnet_group in subnet_groups
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
