#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_placement_group_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 placement groups
description:
  - Gathers information about EC2 placement groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 placement groups.
      - Filter names and values are passed to the EC2 C(DescribePlacementGroups) API.
      - Boolean and numeric values, including list entries, are converted to strings.
    type: dict
  group_ids:
    description:
      - EC2 placement group IDs used to limit the result set.
      - Placement groups shared with the account are included; EC2 describes
        them only by ID.
      - When O(group_names) or O(filters) are also set, only groups that match
        them are returned.
      - An ID that does not exist results in no entry; no error is raised.
    elements: str
    type: list
  group_names:
    description:
      - EC2 placement group names used to limit the result set.
      - This is sent as the C(group-name) filter and takes precedence over a
        C(group-name) key in O(filters).
      - EC2 accepts at most 200 filter values in each request, counted across all
        filters, so this list is split across requests and O(filters) must contain
        fewer than 200 values when this is set.
      - A name that does not exist results in no entry; no error is raised.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only retrieves information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about EC2 placement groups
  linuxhq.aws.ec2_placement_group_info:

- name: Gather information about selected EC2 placement groups
  linuxhq.aws.ec2_placement_group_info:
    group_names:
      - example-placement-group

- name: Gather information about EC2 placement groups using filters
  linuxhq.aws.ec2_placement_group_info:
    filters:
      strategy: cluster
"""

RETURN = r"""
placement_groups:
  description:
    - A list of EC2 placement groups.
  returned: always
  type: list
  elements: dict
  contains:
    group_arn:
      description: ARN of the placement group.
      returned: when available
      type: str
    group_id:
      description: ID of the placement group.
      returned: always
      type: str
    group_name:
      description: Name of the placement group.
      returned: always
      type: str
    linked_group_id:
      description: ID of the placement group linked to this one.
      returned: when available
      type: str
    operator:
      description: Details of the service that operates the placement group.
      returned: when available
      type: dict
    parent_group_id:
      description: ID of the parent placement group.
      returned: when available
      type: str
    partition_count:
      description: Number of partitions in a C(partition) placement group.
      returned: when available
      type: int
    spread_level:
      description: Spread level of a C(spread) placement group, C(host) or C(rack).
      returned: when available
      type: str
    state:
      description: State of the placement group.
      returned: always
      type: str
    strategy:
      description: Strategy of the placement group.
      returned: always
      type: str
    tags:
      description:
        - Tags of the placement group.
        - Tag keys keep their original case.
      returned: when available
      type: dict
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    ansible_dict_to_string_filter_list,
    filter_value_batches,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)

# EC2 returns InvalidParameterValue for an ID that never existed or is malformed,
# and InvalidPlacementGroup.Unknown for a recently deleted group.
GROUP_ID_NOT_FOUND_CODES = ("InvalidParameterValue", "InvalidPlacementGroup.Unknown")


def describe_placement_group_by_id(client, module, group_id, request):
    """Return the placement groups EC2 describes for one ID, or none when the ID does not exist."""
    try:
        response = client.describe_placement_groups(GroupIds=[group_id], aws_retry=True, **request)
    except is_boto3_error_code(GROUP_ID_NOT_FOUND_CODES):
        return []
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe EC2 placement group {group_id}")

    return response.get("PlacementGroups", [])


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "group_ids": {"elements": "str", "type": "list"},
        "group_names": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    filters = dict(module.params["filters"] or {})
    group_ids = list(dict.fromkeys(module.params["group_ids"] or []))
    group_names = list(dict.fromkeys(module.params["group_names"] or []))

    # GroupNames and GroupIds fail for a group that does not exist, so names are
    # filtered by the documented group-name filter and IDs are matched locally.
    # Shared groups are described only by ID, so unmatched IDs are described one at a time.
    requests = []
    for batch_filters in filter_value_batches(module, filters, "group-name", group_names, "group_names"):
        request = {}
        if batch_filters:
            request["Filters"] = ansible_dict_to_string_filter_list(batch_filters)

        requests.append(request)

    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_placement_groups": tuple(requests[0])},
    )

    placement_groups = []
    for request in requests:
        placement_groups.extend(
            query_list(
                module,
                client,
                "describe_placement_groups",
                "PlacementGroups",
                "Unable to describe EC2 placement groups",
                **request,
            )
        )

    if any(not isinstance(placement_group, dict) for placement_group in placement_groups):
        module.fail_json(msg="EC2 returned invalid placement group information")

    if group_ids:
        placement_groups = [
            placement_group for placement_group in placement_groups if placement_group.get("GroupId") in group_ids
        ]
        found_group_ids = {placement_group.get("GroupId") for placement_group in placement_groups}
        unmatched_group_ids = [group_id for group_id in group_ids if group_id not in found_group_ids]

        if unmatched_group_ids:
            require_client_methods(
                module,
                client,
                "EC2",
                {"describe_placement_groups": tuple(requests[0]) + ("GroupIds",)},
            )

        for group_id in unmatched_group_ids:
            # A group matches at most one group-name batch, so stop at the first match.
            for request in requests:
                shared_groups = describe_placement_group_by_id(client, module, group_id, request)
                if any(not isinstance(placement_group, dict) for placement_group in shared_groups):
                    module.fail_json(msg="EC2 returned invalid placement group information")

                matches = [
                    placement_group for placement_group in shared_groups if placement_group.get("GroupId") == group_id
                ]
                if matches:
                    placement_groups.extend(matches)
                    break

    module.exit_json(
        changed=False,
        placement_groups=boto3_resource_list_to_ansible_dict(placement_groups, transform_tags=True, force_tags=False),
    )


if __name__ == "__main__":
    main()
