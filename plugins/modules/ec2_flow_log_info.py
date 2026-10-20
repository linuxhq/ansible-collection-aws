#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_flow_log_info
version_added: "1.9.0"
short_description: Gather information about AWS EC2 flow logs
description:
  - Gathers information about EC2 flow logs.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 flow logs.
      - Filter names and values are passed to the EC2 C(DescribeFlowLogs) API.
      - Boolean and numeric values, including list entries, are converted to strings.
    type: dict
  flow_log_ids:
    description:
      - EC2 flow log IDs used to limit the result set.
      - The module sends at most 100 IDs in each request.
    elements: str
    type: list
  resource_ids:
    description:
      - Resource IDs used to limit the result set.
      - This is added as a C(resource-id) EC2 flow log filter.
      - This overrides a C(resource-id) entry in O(filters).
      - EC2 accepts at most 200 filter values in each request, counted across all
        filters, so this list is split across requests and O(filters) must contain
        fewer than 200 values when this is set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module does not modify AWS resources.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about all EC2 flow logs
  linuxhq.aws.ec2_flow_log_info:

- name: Gather information about selected EC2 flow logs
  linuxhq.aws.ec2_flow_log_info:
    flow_log_ids:
      - fl-0123456789abcdef0

- name: Gather information about flow logs for a VPC
  linuxhq.aws.ec2_flow_log_info:
    resource_ids:
      - vpc-0123456789abcdef0

- name: Gather information about successfully delivering accepted-traffic flow logs
  linuxhq.aws.ec2_flow_log_info:
    filters:
      deliver-log-status: SUCCESS
      traffic-type: ACCEPT
"""

RETURN = r"""
flow_logs:
  description:
    - A list of EC2 flow logs.
  returned: always
  type: list
  elements: dict
  contains:
    creation_time:
      description: Date and time the flow log was created.
      returned: when available
      type: str
    deliver_cross_account_role:
      description: ARN of the IAM role that publishes flow logs across accounts.
      returned: when available
      type: str
    deliver_logs_error_message:
      description: Information about a log delivery error.
      returned: when available
      type: str
    deliver_logs_permission_arn:
      description: ARN of the IAM role that publishes logs to CloudWatch Logs.
      returned: when available
      type: str
    deliver_logs_status:
      description: Status of the log delivery, C(SUCCESS) or C(FAILED).
      returned: when available
      type: str
    destination_options:
      description: Destination options for flow logs delivered to Amazon S3.
      returned: when available
      type: dict
      contains:
        file_format:
          description: Format of the flow log records.
          returned: when available
          type: str
        hive_compatible_partitions:
          description: Whether Hive-compatible prefixes are used.
          returned: when available
          type: bool
        per_hour_partition:
          description: Whether logs are partitioned per hour.
          returned: when available
          type: bool
    flow_log_id:
      description: ID of the flow log.
      returned: always
      type: str
    flow_log_status:
      description: Status of the flow log.
      returned: when available
      type: str
    log_destination:
      description: ARN of the destination for the flow log data.
      returned: when available
      type: str
    log_destination_type:
      description: Type of destination for the flow log data.
      returned: when available
      type: str
    log_format:
      description: Format of the flow log records.
      returned: when available
      type: str
    log_group_name:
      description: Name of the CloudWatch Logs log group.
      returned: when available
      type: str
    max_aggregation_interval:
      description: Maximum interval, in seconds, during which packets are aggregated into a flow log record.
      returned: when available
      type: int
    resource_id:
      description: ID of the monitored resource.
      returned: when available
      type: str
    tag_field_specifications:
      description: Tag configuration for EC2 tag fields in a custom log format.
      returned: when available
      type: list
      elements: dict
    tags:
      description:
        - Tags of the flow log.
        - Tag keys keep their original case.
      returned: when available
      type: dict
    traffic_type:
      description: Type of traffic captured by the flow log.
      returned: when available
      type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.iterators import chunks
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

# The EC2 model documents 1000 flow log IDs per call, but DescribeFlowLogs returns InternalError above 100.
MAX_FLOW_LOG_IDS_PER_REQUEST = 100


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "flow_log_ids": {"elements": "str", "type": "list"},
        "resource_ids": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    flow_log_ids = list(dict.fromkeys(module.params["flow_log_ids"] or []))
    resource_ids = list(dict.fromkeys(module.params["resource_ids"] or []))
    filters = dict(module.params["filters"] or {})

    describe_parameters = []
    if flow_log_ids:
        describe_parameters.append("FlowLogIds")

    if resource_ids or filters:
        describe_parameters.append("Filter")

    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_flow_logs": tuple(describe_parameters) + ("MaxResults", "NextToken")},
    )

    # Each request covers one batch of IDs and one batch of filters, so together they cover every pair.
    # Flow log IDs do not count toward the EC2 filter value limit.
    flow_log_id_batches = list(chunks(flow_log_ids, MAX_FLOW_LOG_IDS_PER_REQUEST)) or [None]
    filter_batches = filter_value_batches(module, filters, "resource-id", resource_ids, "resource_ids")
    flow_logs = []
    for flow_log_id_batch in flow_log_id_batches:
        for batch_filters in filter_batches:
            request = {}
            if flow_log_id_batch:
                request["FlowLogIds"] = flow_log_id_batch

            if batch_filters:
                request["Filter"] = ansible_dict_to_string_filter_list(batch_filters)

            flow_logs.extend(
                query_list(
                    module,
                    client,
                    "describe_flow_logs",
                    "FlowLogs",
                    "Unable to describe EC2 flow logs",
                    **request,
                )
            )

    if any(not isinstance(flow_log, dict) for flow_log in flow_logs):
        module.fail_json(msg="AWS returned an invalid EC2 flow log")

    module.exit_json(
        changed=False,
        flow_logs=boto3_resource_list_to_ansible_dict(flow_logs, transform_tags=True, force_tags=False),
    )


if __name__ == "__main__":
    main()
