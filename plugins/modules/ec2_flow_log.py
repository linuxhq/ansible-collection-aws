#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_flow_log
version_added: "1.9.0"
short_description: Manage AWS EC2 flow logs
description:
  - Creates and deletes EC2 flow logs for VPC, subnet, network interface,
    regional NAT gateway, and transit gateway resources.
  - Manages tags on existing matching flow logs.
  - EC2 permits at most 50 tags on a flow log; tag keys may contain at most
    128 characters and tag values at most 256 characters.
  - Existing flow log tags are purged only when O(tags) is provided and
    O(purge_tags=true).
  - EC2 flow logs cannot be modified. When settings change, the module creates a new flow log; set
    O(purge_flow_logs=true) to delete the flow logs on O(resource_ids) that no longer match.
author:
  - Taylor Kimball (@tkimball83)
options:
  deliver_cross_account_role:
    description:
      - The ARN of the IAM role that permits delivery to a cross-account destination.
      - This must not be empty when O(state=present).
    type: str
  deliver_logs_permission_arn:
    description:
      - The ARN of the IAM role that permits delivery to CloudWatch Logs.
      - This is required to create flow logs when O(log_destination_type) is C(cloud-watch-logs), the default
        when O(state=present).
      - This must not be empty when O(state=present).
    type: str
  destination_options:
    description:
      - Destination options for flow logs delivered to Amazon S3.
      - Requires O(log_destination_type).
      - O(log_destination_type) must be C(s3) when O(state=present).
      - Requires botocore 1.21.61 or later.
    suboptions:
      file_format:
        description:
          - The format for the flow log.
        choices:
          - plain-text
          - parquet
        type: str
      hive_compatible_partitions:
        description:
          - Whether to use Hive-compatible S3 prefixes.
        type: bool
      per_hour_partition:
        description:
          - Whether to partition S3 delivered flow logs by hour.
        type: bool
    type: dict
  log_destination:
    description:
      - The ARN of the destination for flow log data.
      - This is commonly used with S3, CloudWatch Logs, or Kinesis Data Firehose destinations.
      - This is required to create flow logs when O(log_destination_type) is C(s3) or C(kinesis-data-firehose).
      - When O(log_destination_type) is C(cloud-watch-logs), this or O(log_group_name) is required to create
        flow logs.
      - This is mutually exclusive with O(log_group_name).
      - This must not be empty when O(state=present).
    type: str
  log_destination_type:
    description:
      - The destination type for flow log data.
      - Defaults to C(cloud-watch-logs) when O(state=present).
    choices:
      - cloud-watch-logs
      - s3
      - kinesis-data-firehose
    type: str
  log_format:
    description:
      - The fields to include in flow log records.
      - This must not be empty when O(state=present).
    type: str
  log_group_name:
    description:
      - The CloudWatch Logs log group name for flow log data.
      - When O(log_destination_type) is C(cloud-watch-logs), this or O(log_destination) is required to create
        flow logs.
      - This is mutually exclusive with O(log_destination).
      - This must not be empty when O(state=present).
    type: str
  max_aggregation_interval:
    description:
      - The maximum interval, in seconds, during which packets are captured and aggregated.
      - This must be C(60) when O(resource_type) is C(TransitGateway) or C(TransitGatewayAttachment).
    choices:
      - 60
      - 600
    type: int
  purge_flow_logs:
    description:
      - Whether to delete flow logs on O(resource_ids) that do not match the requested settings.
      - Replacement flow logs are created before the old ones are deleted, so logging continues.
      - Old flow logs are kept, and the module fails, when a replacement is not active or reports failed
        delivery. They are also kept, with a warning, when EC2 does not yet return a new replacement.
      - Delivery failures that EC2 reports only after the first delivery attempt cannot be detected.
      - This is only used when O(state=present).
    default: false
    type: bool
    version_added: "2.6.0"
  resource_ids:
    description:
      - The IDs of the resources for which flow logs are managed.
      - This list must contain at least one entry.
    elements: str
    required: true
    type: list
  resource_type:
    description:
      - The type of resource for which to create flow logs.
      - This is required when O(state=present).
    choices:
      - VPC
      - Subnet
      - NetworkInterface
      - TransitGateway
      - TransitGatewayAttachment
      - RegionalNatGateway
    type: str
  state:
    description:
      - Whether matching EC2 flow logs should exist.
      - When O(state=absent), only specified attributes are used to match flow logs.
      - If only O(resource_ids) is set, all flow logs for those resources are removed.
    choices:
      - absent
      - present
    default: present
    type: str
  traffic_type:
    description:
      - The type of traffic to log.
      - This is not supported when O(resource_type) is C(TransitGateway) or C(TransitGatewayAttachment).
      - Defaults to C(ALL) when O(state=present) and O(resource_type) is C(VPC), C(Subnet),
        C(NetworkInterface), or C(RegionalNatGateway).
    choices:
      - ACCEPT
      - REJECT
      - ALL
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts flow log creation, deletion, and tag changes without modifying AWS resources.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Ensure VPC flow logs are delivered to CloudWatch Logs
  linuxhq.aws.ec2_flow_log:
    resource_ids:
      - vpc-0123456789abcdef0
    resource_type: VPC
    traffic_type: ALL
    log_group_name: /aws/vpc/flow-logs
    deliver_logs_permission_arn: arn:aws:iam::123456789012:role/vpc-flow-logs
    tags:
      Name: vpc-flow-logs

- name: Ensure subnet flow logs are delivered to S3
  linuxhq.aws.ec2_flow_log:
    resource_ids:
      - subnet-0123456789abcdef0
    resource_type: Subnet
    log_destination_type: s3
    log_destination: arn:aws:s3:::example-flow-logs
    destination_options:
      file_format: parquet
      hive_compatible_partitions: true
      per_hour_partition: true

- name: Ensure flow logs are absent from a VPC
  linuxhq.aws.ec2_flow_log:
    resource_ids:
      - vpc-0123456789abcdef0
    state: absent
"""

RETURN = r"""
deleted_flow_log_ids:
  description:
    - The EC2 flow log IDs deleted by O(purge_flow_logs=true), or that would be deleted in check mode.
  returned: when O(state=present)
  type: list
  elements: str
  version_added: "2.6.0"
flow_log_ids:
  description:
    - The matching EC2 flow log IDs.
  returned: always
  type: list
  elements: str
flow_logs:
  description:
    - The matching EC2 flow logs after module execution.
    - A created flow log that EC2 has not returned yet contains only RV(flow_logs[].flow_log_id).
  returned: when O(state=present)
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
      returned: except for flow logs that would be created in check mode
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
resource_ids:
  description:
    - The requested resource IDs.
  returned: always
  type: list
  elements: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import uuid

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.arn import parse_aws_arn
from ansible_collections.amazon.aws.plugins.module_utils.botocore import is_boto3_error_code
from ansible_collections.amazon.aws.plugins.module_utils.iterators import chunks
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    boto3_tag_specifications,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import MAX_FILTER_VALUES_PER_REQUEST
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    ec2_tag_methods,
    reconcile_ec2_tags,
    require_resulting_tag_limit,
    require_valid_tags,
)

# The EC2 model documents 1000 IDs, but DeleteFlowLogs and DescribeFlowLogs return InternalError above 100.
MAX_FLOW_LOG_IDS_PER_REQUEST = 100
# EC2 rejects more resource IDs per CreateFlowLogs call.
MAX_RESOURCE_IDS_PER_CREATE = 300
MAX_TRANSIT_GATEWAY_RESOURCE_IDS_PER_CREATE = 25

ABSENT_MATCH_FIELDS = (
    "deliver_cross_account_role",
    "deliver_logs_permission_arn",
    "log_destination",
    "log_destination_type",
    "log_format",
    "log_group_name",
    "max_aggregation_interval",
    "traffic_type",
)

PRESENT_MATCH_FIELDS = (
    "deliver_cross_account_role",
    "deliver_logs_permission_arn",
    "log_destination",
    "log_format",
    "log_group_name",
    "max_aggregation_interval",
)

# EC2 requires TrafficType for every resource type except the transit gateway types.
TRAFFIC_TYPE_RESOURCE_TYPES = (
    "VPC",
    "Subnet",
    "NetworkInterface",
    "RegionalNatGateway",
)

TRANSIT_GATEWAY_RESOURCE_TYPES = (
    "TransitGateway",
    "TransitGatewayAttachment",
)

# EC2 stores these documented defaults for omitted S3 destination options and returns all three.
S3_DESTINATION_OPTION_DEFAULTS = {
    "file_format": "plain-text",
    "hive_compatible_partitions": False,
    "per_hour_partition": False,
}


def normalized_resource_ids(module):
    return list(dict.fromkeys(module.params["resource_ids"] or []))


def comparable_destination_options(module):
    return {key: value for key, value in (module.params["destination_options"] or {}).items() if value is not None}


def desired_match_fields(module, fields):
    desired = {field: module.params[field] for field in fields if module.params[field] is not None}
    destination_options = comparable_destination_options(module)
    if destination_options:
        desired["destination_options"] = destination_options

    return desired


def matching_flow_logs(module, flow_logs, desired):
    resource_ids = set(normalized_resource_ids(module))
    matching = []
    for flow_log in flow_logs:
        if not isinstance(flow_log, dict):
            module.fail_json(msg="AWS returned an invalid EC2 flow log")

        if flow_log.get("ResourceId") not in resource_ids:
            continue

        normalized = boto3_resource_to_ansible_dict(flow_log, transform_tags=False, force_tags=False)
        comparable = {key: normalized.get(key) for key in desired}
        if "destination_options" in desired:
            current_destination_options = normalized.get("destination_options") or {}
            comparable["destination_options"] = {
                option_key: current_destination_options.get(option_key) for option_key in desired["destination_options"]
            }

        if comparable != desired:
            continue

        flow_log_id = flow_log.get("FlowLogId")
        if not isinstance(flow_log_id, str) or not flow_log_id:
            module.fail_json(msg="AWS returned an invalid matching EC2 flow log without a flow log ID")

        matching.append(flow_log)

    return matching


def get_flow_logs(client, module):
    flow_logs = []
    for batch in chunks(normalized_resource_ids(module), MAX_FILTER_VALUES_PER_REQUEST):
        flow_logs.extend(
            query_list(
                module,
                client,
                "describe_flow_logs",
                "FlowLogs",
                f"Unable to describe EC2 flow logs for resources {', '.join(batch)}",
                Filter=ansible_dict_to_boto3_filter_list({"resource-id": batch}),
            )
        )

    return flow_logs


def delete_flow_logs(client, module, flow_log_ids, changed=False):
    """Delete flow logs and return the IDs that were removed.

    changed reports whether resources were already modified, for failure results.
    """
    require_client_methods(
        module,
        client,
        "EC2",
        {"delete_flow_logs": ("FlowLogIds",)},
    )
    removed = []
    unsuccessful = []
    for batch in chunks(flow_log_ids, MAX_FLOW_LOG_IDS_PER_REQUEST):
        try:
            response = client.delete_flow_logs(
                FlowLogIds=batch,
                aws_retry=True,
            )
        except is_boto3_error_code("InvalidFlowLogId.NotFound"):
            # EC2 rejects the whole request when any flow log is already gone, so delete only those that remain.
            require_client_methods(
                module,
                client,
                "EC2",
                {"describe_flow_logs": ("FlowLogIds",)},
                changed=changed or bool(removed),
            )
            remaining = query_list(
                module,
                client,
                "describe_flow_logs",
                "FlowLogs",
                f"Unable to describe EC2 flow logs {', '.join(batch)}",
                changed=changed or bool(removed),
                FlowLogIds=batch,
            )
            remaining_ids = {flow_log.get("FlowLogId") for flow_log in remaining if isinstance(flow_log, dict)}
            batch = [flow_log_id for flow_log_id in batch if flow_log_id in remaining_ids]
            if not batch:
                continue

            try:
                response = client.delete_flow_logs(
                    FlowLogIds=batch,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e, changed=changed or bool(removed), msg=f"Unable to delete EC2 flow logs {', '.join(batch)}"
                )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e, changed=changed or bool(removed), msg=f"Unable to delete EC2 flow logs {', '.join(batch)}"
            )

        failures = response.get("Unsuccessful", [])
        failed_flow_log_ids = {failure.get("ResourceId") for failure in failures}
        removed.extend(flow_log_id for flow_log_id in batch if flow_log_id not in failed_flow_log_ids)
        unsuccessful.extend(
            failure for failure in failures if (failure.get("Error") or {}).get("Code") != "InvalidFlowLogId.NotFound"
        )

    if unsuccessful:
        module.fail_json(
            changed=changed or bool(removed),
            msg="Unable to delete one or more EC2 flow logs",
            unsuccessful=boto3_resource_list_to_ansible_dict(unsuccessful, transform_tags=False, force_tags=False),
        )

    return removed


def verified_purge(module, flow_logs, current, purge_flow_log_ids, changed=False):
    """Return the flow logs that are safe to delete because their replacements are working.

    changed reports whether resources were already modified, for failure results.
    """
    purge_resource_ids = {
        flow_log.get("ResourceId") for flow_log in flow_logs if flow_log.get("FlowLogId") in purge_flow_log_ids
    }
    replacements = [flow_log for flow_log in current if flow_log.get("ResourceId") in purge_resource_ids]
    failed = sorted(
        flow_log["FlowLogId"]
        for flow_log in replacements
        if flow_log.get("DeliverLogsStatus") == "FAILED" or flow_log.get("FlowLogStatus") not in (None, "ACTIVE")
    )
    if failed:
        module.fail_json(
            changed=changed,
            msg=(
                f"Replacement EC2 flow logs {', '.join(failed)} are not delivering logs; "
                f"superseded flow logs {', '.join(purge_flow_log_ids)} were kept"
            ),
            replacement_errors={
                flow_log["FlowLogId"]: flow_log.get("DeliverLogsErrorMessage")
                for flow_log in replacements
                # Flow logs predicted in check mode have no ID.
                if flow_log.get("FlowLogId") in failed
            },
        )

    # Created flow logs that describe_flow_logs has not returned yet only carry their ID.
    covered = {flow_log.get("ResourceId") for flow_log in replacements}
    if purge_resource_ids - covered:
        module.warn(
            "EC2 has not returned the replacement flow logs yet; "
            f"superseded flow logs {', '.join(purge_flow_log_ids)} were kept and will be purged on a later run"
        )
        return []

    return purge_flow_log_ids


def require_create_parameters(module, desired):
    """Fail before any write when EC2 would reject creating flow logs with the desired settings."""
    log_destination_type = desired["log_destination_type"]
    if log_destination_type == "cloud-watch-logs":
        if "deliver_logs_permission_arn" not in desired:
            module.fail_json(
                msg=(
                    "deliver_logs_permission_arn is required to create flow logs "
                    "when log_destination_type is cloud-watch-logs"
                )
            )

        if "log_destination" not in desired and "log_group_name" not in desired:
            module.fail_json(
                msg=(
                    "log_group_name or log_destination is required to create flow logs "
                    "when log_destination_type is cloud-watch-logs"
                )
            )

    elif "log_destination" not in desired:
        module.fail_json(
            msg=f"log_destination is required to create flow logs when log_destination_type is {log_destination_type}"
        )


def ensure_absent(client, module):
    resource_ids = normalized_resource_ids(module)
    desired = desired_match_fields(module, ABSENT_MATCH_FIELDS)
    current = matching_flow_logs(module, get_flow_logs(client, module), desired)

    flow_log_ids = [flow_log["FlowLogId"] for flow_log in current]

    changed = bool(flow_log_ids)

    if changed and not module.check_mode:
        changed = bool(delete_flow_logs(client, module, flow_log_ids))

    module.exit_json(
        changed=changed,
        flow_log_ids=flow_log_ids,
        resource_ids=resource_ids,
        state="absent",
    )


def ensure_present(client, module):
    resource_ids = normalized_resource_ids(module)
    resource_type = module.params["resource_type"]
    tags = module.params["tags"]
    desired = {
        "log_destination_type": module.params["log_destination_type"] or "cloud-watch-logs",
    }
    if resource_type in TRAFFIC_TYPE_RESOURCE_TYPES:
        desired["traffic_type"] = module.params["traffic_type"] or "ALL"

    desired.update(desired_match_fields(module, PRESENT_MATCH_FIELDS))
    destination_options = comparable_destination_options(module)
    flow_logs = get_flow_logs(client, module)
    current = matching_flow_logs(module, flow_logs, desired)

    purge_flow_log_ids = []
    if module.params.get("purge_flow_logs"):
        matched_flow_log_ids = {flow_log["FlowLogId"] for flow_log in current}
        requested_resource_ids = set(resource_ids)
        purge_flow_log_ids = sorted(
            flow_log["FlowLogId"]
            for flow_log in flow_logs
            if flow_log.get("ResourceId") in requested_resource_ids
            and flow_log.get("FlowLogId")
            and flow_log["FlowLogId"] not in matched_flow_log_ids
        )

    matched_resource_ids = {flow_log.get("ResourceId") for flow_log in current}
    missing_resource_ids = [resource_id for resource_id in resource_ids if resource_id not in matched_resource_ids]
    if missing_resource_ids:
        require_create_parameters(module, desired)

    tags_changed = []
    if tags is not None:
        for flow_log in current:
            current_tags = boto3_tag_list_to_ansible_dict(flow_log.get("Tags", []))
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                current_tags,
                tags,
                purge_tags=module.params["purge_tags"],
            )
            require_resulting_tag_limit(module, current_tags, tags_to_set, tag_keys_to_unset, 50, "EC2 flow log")

            if tags_to_set or tag_keys_to_unset:
                tags_changed.append((flow_log, tags_to_set, tag_keys_to_unset))

    changed = bool(missing_resource_ids or tags_changed or purge_flow_log_ids)
    # Whether AWS was already modified, so failures after a mutation report changed=True.
    modified = False

    if changed and not module.check_mode:
        # Check every later operation first so an SDK gap fails before AWS is modified.
        later_methods = ec2_tag_methods(
            any(tags_to_set for _flow_log, tags_to_set, _tag_keys_to_unset in tags_changed),
            any(tag_keys_to_unset for _flow_log, _tags_to_set, tag_keys_to_unset in tags_changed),
        )

        if purge_flow_log_ids:
            later_methods["delete_flow_logs"] = ("FlowLogIds",)

        require_client_methods(module, client, "EC2", later_methods)

    if missing_resource_ids:
        if not module.check_mode:
            base_request = snake_dict_to_camel_dict(dict(desired, resource_type=resource_type), capitalize_first=True)
            tag_specifications = boto3_tag_specifications(tags, types="vpc-flow-log")
            if tag_specifications is not None:
                base_request["TagSpecifications"] = tag_specifications

            require_client_methods(
                module,
                client,
                "EC2",
                {"create_flow_logs": tuple(base_request) + ("ClientToken", "ResourceIds")},
            )

            if "DestinationOptions" in base_request:
                destination_option_parameters = (
                    client.meta.service_model.operation_model("CreateFlowLogs")
                    .input_shape.members["DestinationOptions"]
                    .members
                )
                for parameter_name in sorted(base_request["DestinationOptions"]):
                    if parameter_name not in destination_option_parameters:
                        module.fail_json(
                            msg=(
                                "Installed botocore does not support EC2 "
                                "create_flow_logs DestinationOptions parameter "
                                f"{parameter_name}"
                            )
                        )

            batch_size = MAX_RESOURCE_IDS_PER_CREATE
            if resource_type in TRANSIT_GATEWAY_RESOURCE_TYPES:
                batch_size = MAX_TRANSIT_GATEWAY_RESOURCE_IDS_PER_CREATE

            created_flow_log_ids = []
            for batch in chunks(missing_resource_ids, batch_size):
                # One token per request makes SDK retries of a request that already succeeded idempotent.
                request = dict(base_request, ResourceIds=batch, ClientToken=str(uuid.uuid4()))

                try:
                    response = client.create_flow_logs(**request, aws_retry=True)
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        changed=modified,
                        msg=f"Unable to create EC2 flow logs for resources {', '.join(batch)}",
                    )

                unsuccessful = response.get("Unsuccessful", [])
                batch_flow_log_ids = response.get("FlowLogIds", [])

                if unsuccessful:
                    module.fail_json(
                        changed=modified or bool(batch_flow_log_ids),
                        msg="Unable to create EC2 flow logs for one or more resources",
                        unsuccessful=boto3_resource_list_to_ansible_dict(
                            unsuccessful, transform_tags=False, force_tags=False
                        ),
                    )

                # The create request succeeded, so AWS may have created flow logs.
                modified = True

                if (
                    not isinstance(batch_flow_log_ids, list)
                    or not batch_flow_log_ids
                    or any(not isinstance(flow_log_id, str) or not flow_log_id for flow_log_id in batch_flow_log_ids)
                ):
                    module.fail_json(
                        changed=modified,
                        msg=f"AWS did not return valid created EC2 flow log IDs for resources {', '.join(batch)}",
                    )

                created_flow_log_ids.extend(batch_flow_log_ids)

            created_flow_logs = []
            for batch in chunks(created_flow_log_ids, MAX_FLOW_LOG_IDS_PER_REQUEST):
                created_flow_logs.extend(
                    query_list(
                        module,
                        client,
                        "describe_flow_logs",
                        "FlowLogs",
                        f"Unable to describe EC2 flow logs {', '.join(batch)}",
                        changed=modified,
                        FlowLogIds=batch,
                    )
                )

            if any(not isinstance(flow_log, dict) for flow_log in created_flow_logs):
                module.fail_json(changed=modified, msg="AWS returned an invalid created EC2 flow log")

            described_ids = {flow_log.get("FlowLogId") for flow_log in created_flow_logs}
            created_flow_logs.extend(
                {"FlowLogId": flow_log_id} for flow_log_id in created_flow_log_ids if flow_log_id not in described_ids
            )

            current = current + created_flow_logs
        else:
            # Predict each flow log as EC2 returns it, with the values EC2 stores for omitted settings.
            predicted = {"max_aggregation_interval": 600}
            if resource_type in TRANSIT_GATEWAY_RESOURCE_TYPES:
                predicted["max_aggregation_interval"] = 60

            predicted.update(desired)
            if desired["log_destination_type"] == "s3":
                predicted["destination_options"] = dict(S3_DESTINATION_OPTION_DEFAULTS, **destination_options)

            if desired["log_destination_type"] == "cloud-watch-logs" and "log_destination" in desired:
                arn = parse_aws_arn(desired["log_destination"]) or {}
                if arn.get("service") == "logs" and arn.get("resource_type") == "log-group":
                    # EC2 also returns the log group name, without the ":*" suffix, for a log group ARN destination.
                    predicted["log_group_name"] = arn["resource_id"].split(":")[0]

            for resource_id in missing_resource_ids:
                flow_log = dict(
                    predicted,
                    flow_log_status="ACTIVE",
                    resource_id=resource_id,
                )
                flow_log = snake_dict_to_camel_dict(flow_log, capitalize_first=True)
                # EC2 returns an empty tag list for an untagged flow log.
                flow_log["Tags"] = ansible_dict_to_boto3_tag_list(tags or {})

                current.append(flow_log)

    if tags_changed and not module.check_mode:
        delete_groups = {}
        create_groups = {}
        for flow_log, tags_to_set, tag_keys_to_unset in tags_changed:
            if tag_keys_to_unset:
                group = tuple(sorted(tag_keys_to_unset))
                delete_groups.setdefault(group, []).append(flow_log["FlowLogId"])

            if tags_to_set:
                group = tuple(sorted(tags_to_set.items()))
                create_groups.setdefault(group, []).append(flow_log["FlowLogId"])

        for tag_keys_to_unset, delete_resources in delete_groups.items():
            reconcile_ec2_tags(
                module, client, delete_resources, {}, tag_keys_to_unset, "EC2 flow logs", changed=modified
            )
            modified = True

        for tags_to_set, create_resources in create_groups.items():
            reconcile_ec2_tags(
                module, client, create_resources, dict(tags_to_set), [], "EC2 flow logs", changed=modified
            )
            modified = True

    for flow_log, tags_to_set, tag_keys_to_unset in tags_changed:
        flow_log.update(apply_tag_deltas(flow_log, tags_to_set, tag_keys_to_unset))

    # Delete superseded flow logs only after their replacements exist and are delivering.
    if purge_flow_log_ids:
        purge_flow_log_ids = verified_purge(module, flow_logs, current, purge_flow_log_ids, changed=modified)
        if purge_flow_log_ids and not module.check_mode:
            purge_flow_log_ids = delete_flow_logs(client, module, purge_flow_log_ids, changed=modified)
            modified = modified or bool(purge_flow_log_ids)

    if not module.check_mode:
        # Report only work AWS performed, such as flow logs that were already gone when deleted.
        changed = modified

    flow_log_ids = [flow_log["FlowLogId"] for flow_log in current if flow_log.get("FlowLogId")]

    module.exit_json(
        changed=changed,
        deleted_flow_log_ids=purge_flow_log_ids,
        flow_log_ids=flow_log_ids,
        flow_logs=boto3_resource_list_to_ansible_dict(current, transform_tags=True, force_tags=False),
        resource_ids=resource_ids,
        state="present",
    )


def main():
    argument_spec = {
        "deliver_cross_account_role": {"type": "str"},
        "deliver_logs_permission_arn": {"type": "str"},
        "destination_options": {
            "options": {
                "file_format": {
                    "choices": ["plain-text", "parquet"],
                    "type": "str",
                },
                "hive_compatible_partitions": {"type": "bool"},
                "per_hour_partition": {"type": "bool"},
            },
            "type": "dict",
        },
        "log_destination": {"type": "str"},
        "log_destination_type": {
            "choices": ["cloud-watch-logs", "s3", "kinesis-data-firehose"],
            "type": "str",
        },
        "log_format": {"type": "str"},
        "log_group_name": {"type": "str"},
        "max_aggregation_interval": {"choices": [60, 600], "type": "int"},
        "purge_flow_logs": {"default": False, "type": "bool"},
        "purge_tags": {"default": True, "type": "bool"},
        "resource_ids": {"elements": "str", "required": True, "type": "list"},
        "resource_type": {
            "choices": [
                "VPC",
                "Subnet",
                "NetworkInterface",
                "TransitGateway",
                "TransitGatewayAttachment",
                "RegionalNatGateway",
            ],
            "type": "str",
        },
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
        "traffic_type": {"choices": ["ACCEPT", "REJECT", "ALL"], "type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["log_destination", "log_group_name"]],
        required_by={"destination_options": ["log_destination_type"]},
        required_if=[("state", "present", ["resource_type"])],
        supports_check_mode=True,
    )
    state = module.params["state"]
    resource_ids = normalized_resource_ids(module)
    resource_type = module.params["resource_type"]
    destination_options = comparable_destination_options(module)

    if not resource_ids:
        module.fail_json(msg="resource_ids must contain at least one item")

    if state == "present":
        # EC2 rejects these blank values, or accepts a whitespace-only value without storing it, so no flow log ever
        # matches them, and check mode would predict new flow logs and a purge.
        for option in (
            "deliver_cross_account_role",
            "deliver_logs_permission_arn",
            "log_destination",
            "log_format",
            "log_group_name",
        ):
            if module.params[option] is not None and not module.params[option].strip():
                module.fail_json(msg=f"{option} must not be empty")

        if module.params["traffic_type"] is not None and resource_type in TRANSIT_GATEWAY_RESOURCE_TYPES:
            module.fail_json(
                msg="traffic_type is not supported when resource_type is TransitGateway or TransitGatewayAttachment"
            )

        if module.params["max_aggregation_interval"] == 600 and resource_type in TRANSIT_GATEWAY_RESOURCE_TYPES:
            module.fail_json(
                msg="max_aggregation_interval must be 60 when resource_type is TransitGateway or TransitGatewayAttachment"
            )

        if destination_options and module.params["log_destination_type"] != "s3":
            module.fail_json(msg="destination_options requires log_destination_type to be s3 when state is present")

    require_valid_tags(module, module.params["tags"] if state == "present" else None, 50)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())
    describe_parameters = ["Filter", "MaxResults", "NextToken"]
    if state == "present":
        describe_parameters.append("FlowLogIds")

    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_flow_logs": tuple(describe_parameters)},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
