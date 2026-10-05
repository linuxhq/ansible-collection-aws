#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_prefix_list_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 VPC prefix lists
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
      - This is sent as the C(prefix-list-id) filter and takes precedence over
        a C(prefix-list-id) key in O(filters).
      - An ID that does not exist results in no entry; no error is raised.
    elements: str
    type: list
  target_version:
    description:
      - The version of the managed prefix list for which to return entries.
      - When omitted, the current version entries are returned.
      - AWS-managed prefix lists are not versioned, so their current entries are
        returned regardless of this option.
      - This must be 1 or greater.
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only gathers information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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
  contains:
    address_family:
      description: The IP address version of the prefix list.
      returned: always
      type: str
      sample: IPv4
    entries:
      description: The prefix list entries.
      returned: always
      type: list
      elements: dict
      contains:
        cidr:
          description: The CIDR block.
          returned: always
          type: str
          sample: 10.0.0.0/16
        description:
          description: The entry description.
          returned: when the entry has a description
          type: str
    ipam_prefix_list_resolver_sync_enabled:
      description: Whether synchronization with an IPAM prefix list resolver is enabled.
      returned: when returned by EC2
      type: bool
    ipam_prefix_list_resolver_target_id:
      description: The ID of the IPAM prefix list resolver target associated with the prefix list.
      returned: when returned by EC2
      type: str
    max_entries:
      description:
        - The maximum number of entries for the prefix list.
        - AWS-managed prefix lists do not return this field.
      returned: when returned by EC2
      type: int
      sample: 10
    owner_id:
      description: The ID of the owner of the prefix list.
      returned: always
      type: str
      sample: "123456789012"
    prefix_list_arn:
      description: The ARN of the prefix list.
      returned: always
      type: str
      sample: arn:aws:ec2:us-east-1:123456789012:prefix-list/pl-0123456789abcdef0
    prefix_list_id:
      description: The ID of the prefix list.
      returned: always
      type: str
      sample: pl-0123456789abcdef0
    prefix_list_name:
      description: The name of the prefix list.
      returned: always
      type: str
      sample: example
    state:
      description: The current state of the prefix list.
      returned: always
      type: str
      sample: create-complete
    state_message:
      description: The state message.
      returned: when returned by EC2
      type: str
    tags:
      description: The prefix list tags.
      returned: when returned by EC2
      type: dict
    version:
      description:
        - The version of the prefix list.
        - AWS-managed prefix lists do not return this field.
      returned: when returned by EC2
      type: int
      sample: 1
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_prefix_lists(module, prefix_lists):
    for prefix_list in prefix_lists:
        tags = prefix_list.get("Tags") if isinstance(prefix_list, dict) else None
        if (
            not isinstance(prefix_list, dict)
            or not isinstance(prefix_list.get("PrefixListId"), str)
            or not prefix_list["PrefixListId"]
            or (tags is not None and not isinstance(tags, list))
            or (
                isinstance(tags, list)
                and any(
                    not isinstance(tag, dict)
                    or not isinstance(tag.get("Key"), str)
                    or not isinstance(tag.get("Value"), str)
                    for tag in tags
                )
            )
        ):
            module.fail_json(msg="EC2 returned invalid managed prefix lists")

    return prefix_lists


def validate_entries(module, entries):
    if not isinstance(entries, list):
        module.fail_json(msg="EC2 returned invalid managed prefix list entries")

    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("Cidr"), str)
            or not entry["Cidr"]
            or (entry.get("Description") is not None and not isinstance(entry.get("Description"), str))
        ):
            module.fail_json(msg="EC2 returned invalid managed prefix list entries")

    return entries


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "prefix_list_ids": {"elements": "str", "type": "list"},
            "target_version": {"type": "int"},
        },
        supports_check_mode=True,
    )
    filters = dict(module.params["filters"] or {})
    prefix_list_ids = list(dict.fromkeys(module.params["prefix_list_ids"] or []))
    target_version = module.params["target_version"]
    if target_version is not None and target_version < 1:
        module.fail_json(msg="target_version must be 1 or greater")

    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    # PrefixListIds fails for a prefix list that does not exist, so IDs are sent
    # as the documented prefix-list-id filter.
    if prefix_list_ids:
        filters["prefix-list-id"] = prefix_list_ids

    request = {}
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    require_client_methods(
        module,
        client,
        "EC2",
        {
            "describe_managed_prefix_lists": tuple(request) + ("MaxResults", "NextToken"),
        },
    )

    prefix_lists = validate_prefix_lists(
        module,
        query_list(
            module,
            client,
            "describe_managed_prefix_lists",
            "PrefixLists",
            "Unable to describe EC2 VPC managed prefix lists",
            **request,
        ),
    )

    if prefix_lists:
        require_client_methods(
            module,
            client,
            "EC2",
            {
                "get_managed_prefix_list_entries": (
                    "MaxResults",
                    "NextToken",
                    "PrefixListId",
                )
                + (("TargetVersion",) if target_version is not None else ()),
            },
        )

    result_prefix_lists = []
    for prefix_list in prefix_lists:
        entry_request = {"PrefixListId": prefix_list["PrefixListId"]}
        # EC2 rejects TargetVersion for AWS-managed prefix lists, which are not versioned.
        if target_version is not None and prefix_list.get("OwnerId") != "AWS":
            entry_request["TargetVersion"] = target_version

        try:
            response = paginated_query_with_retries(
                client,
                "get_managed_prefix_list_entries",
                **entry_request,
            )
        except is_boto3_error_code("InvalidPrefixListID.NotFound"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get EC2 VPC managed prefix list entries for {prefix_list['PrefixListId']}",
            )

        entries = validate_entries(
            module,
            response.get("Entries") if isinstance(response, dict) else None,
        )

        result_prefix_lists.append(
            dict(
                boto3_resource_to_ansible_dict(prefix_list, transform_tags=True, force_tags=False),
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
