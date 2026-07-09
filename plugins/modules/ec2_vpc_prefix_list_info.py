#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_prefix_list_info
short_description: Gather information about aws virtual private cloud prefix lists
description:
  - Gathers information about EC2 VPC managed prefix lists.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 VPC managed prefix lists.
      - Filter names and values are passed to the EC2 C(DescribeManagedPrefixLists) API.
    type: dict
  prefix_list_ids:
    description:
      - EC2 VPC managed prefix list IDs used to limit the result set.
    elements: str
    type: list
  target_version:
    description:
      - The version of the managed prefix list for which to return entries.
      - When omitted, the current version entries are returned.
    type: int
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
    prefix_list_ids:
      - pl-0123456789abcdef0

- name: Gather information about EC2 VPC prefix lists using filters
  linuxhq.aws.ec2_vpc_prefix_list_info:
    filters:
      prefix-list-name: molecule-localhost

- name: Gather information about a selected EC2 VPC prefix list version
  linuxhq.aws.ec2_vpc_prefix_list_info:
    prefix_list_ids:
      - pl-0123456789abcdef0
    target_version: 1
"""

RETURN = r"""
prefix_lists:
  description:
    - A list of EC2 VPC managed prefix lists, including their entries.
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
    boto3_resource_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "prefix_list_ids": {"elements": "str", "type": "list"},
            "target_version": {"type": "int"},
        },
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    filters = module.params["filters"]
    prefix_list_ids = module.params["prefix_list_ids"]
    target_version = module.params["target_version"]

    request = {}
    if prefix_list_ids:
        request["PrefixListIds"] = prefix_list_ids
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    try:
        prefix_lists = paginated_query_with_retries(
            client, "describe_managed_prefix_lists", **request
        ).get("PrefixLists", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 VPC managed prefix lists")

    result_prefix_lists = []
    for prefix_list in prefix_lists:
        entry_request = {"PrefixListId": prefix_list["PrefixListId"]}
        if target_version is not None:
            entry_request["TargetVersion"] = target_version

        try:
            entries = paginated_query_with_retries(
                client,
                "get_managed_prefix_list_entries",
                **entry_request,
            ).get("Entries", [])
        except is_boto3_error_code("InvalidPrefixListID.NotFound"):
            entries = []
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to get EC2 VPC managed prefix list entries for "
                    f"{prefix_list['PrefixListId']}"
                ),
            )

        result_prefix_lists.append(
            dict(
                boto3_resource_to_ansible_dict(
                    prefix_list, transform_tags=True, force_tags=False
                ),
                entries=boto3_resource_list_to_ansible_dict(
                    entries,
                    transform_tags=False,
                    force_tags=False,
                ),
            )
        )

    module.exit_json(
        changed=False,
        prefix_lists=result_prefix_lists,
    )


if __name__ == "__main__":
    main()
