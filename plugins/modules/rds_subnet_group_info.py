#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: rds_subnet_group_info
version_added: '1.9.0'
short_description: Gather information about aws rds subnet groups
description:
  - Gathers information about AWS Relational Database Service (RDS) DB subnet
    groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - RDS DB subnet group name used to limit the result set.
      - This value is passed to the RDS C(DescribeDBSubnetGroups) API
        as C(DBSubnetGroupName).
      - Fails when the subnet group does not exist, as C(DescribeDBSubnetGroups) does.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module does not modify AWS resources.
    support: full
  diff_mode:
    description: This module does not modify AWS resources.
    support: none
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
  elements: dict
  contains:
    db_subnet_group_arn:
      description: The DB subnet group ARN.
      returned: always
      type: str
    db_subnet_group_description:
      description: The DB subnet group description.
      returned: always
      type: str
    db_subnet_group_name:
      description: The DB subnet group name.
      returned: always
      type: str
    subnet_group_status:
      description: The DB subnet group status.
      returned: always
      type: str
      sample: Complete
    subnets:
      description: The subnets in the DB subnet group.
      returned: always
      type: list
      elements: dict
      contains:
        subnet_availability_zone:
          description: The subnet Availability Zone.
          returned: always
          type: dict
        subnet_identifier:
          description: The subnet ID.
          returned: always
          type: str
        subnet_outpost:
          description: The Outpost the subnet belongs to.
          returned: when the subnet is on an Outpost
          type: dict
        subnet_status:
          description: The subnet status.
          returned: always
          type: str
    supported_network_types:
      description: The network types the DB subnet group supports.
      returned: when returned by AWS
      type: list
      elements: str
    tags:
      description: The DB subnet group tags with key case preserved.
      returned: always
      type: dict
    vpc_id:
      description: The VPC ID of the DB subnet group.
      returned: always
      type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import boto3_tag_list_to_ansible_dict
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def subnet_group_tags(client, module, subnet_group):
    arn = subnet_group.get("DBSubnetGroupArn")
    try:
        response = client.list_tags_for_resource(ResourceName=arn, aws_retry=True)
    except is_boto3_error_code("InvalidParameterValue"):
        # RDS reports a subnet group deleted after DescribeDBSubnetGroups as InvalidParameterValue;
        # the ARN comes from that response, so this only occurs when the group disappears.
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to list tags for AWS RDS DB subnet group {arn}")

    tags = response.get("TagList") if isinstance(response, dict) else None
    if not isinstance(tags, list) or any(
        not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str)
        for tag in tags
    ):
        module.fail_json(msg=f"Unable to list tags for AWS RDS DB subnet group {arn}: AWS returned an invalid response")

    return boto3_tag_list_to_ansible_dict(tags)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("rds", retry_decorator=AWSRetry.jittered_backoff())

    name = module.params["name"]
    request = {}
    if name:
        request["DBSubnetGroupName"] = name

    require_client_methods(
        module,
        client,
        "RDS",
        {
            "describe_db_subnet_groups": tuple(request) + ("Marker", "MaxRecords"),
        },
    )

    subnet_groups = query_list(
        module,
        client,
        "describe_db_subnet_groups",
        "DBSubnetGroups",
        "Unable to describe AWS RDS DB subnet groups",
        **request,
    )
    if not isinstance(subnet_groups, list) or any(
        not isinstance(group, dict) or not isinstance(group.get("DBSubnetGroupArn"), str) for group in subnet_groups
    ):
        module.fail_json(msg="Unable to describe AWS RDS DB subnet groups: AWS returned an invalid response")

    if subnet_groups:
        require_client_methods(module, client, "RDS", {"list_tags_for_resource": ("ResourceName",)})

    results = []
    for subnet_group in subnet_groups:
        tags = subnet_group_tags(client, module, subnet_group)
        # A subnet group can be deleted between describing it and listing its tags.
        if tags is None:
            continue

        result = boto3_resource_list_to_ansible_dict([subnet_group], transform_tags=False, force_tags=False)[0]
        result["tags"] = tags
        results.append(result)

    module.exit_json(changed=False, subnet_groups=results)


if __name__ == "__main__":
    main()
