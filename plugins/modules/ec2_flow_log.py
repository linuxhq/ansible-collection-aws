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
  - Tag keys must not be blank. EC2 stores a tag value made only of spaces, tabs,
    carriage returns, and line feeds as an empty value, so such a value is sent,
    compared, and returned as empty.
  - Existing flow log tags are purged only when O(tags) is provided and
    O(purge_tags=true).
  - O(name) identifies the flow log on each of O(resource_ids) by its C(Name) tag. EC2 flow logs cannot be
    modified, so a flow log with this name and other settings is replaced, and flow logs with another C(Name)
    tag or none are never changed or deleted.
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
      - This must not be empty when O(state=present).
      - This is mutually exclusive with O(log_group_name).
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
      - This must not be empty when O(state=present).
      - This is mutually exclusive with O(log_destination).
    type: str
  max_aggregation_interval:
    description:
      - The maximum interval, in seconds, during which packets are captured and aggregated.
      - This must be C(60) when O(resource_type) is C(TransitGateway) or C(TransitGatewayAttachment).
    choices:
      - 60
      - 600
    type: int
  name:
    description:
      - The name of the flow log, managed as its C(Name) tag.
      - This is used in combination with O(resource_ids) to identify one flow log on each resource, and only
        flow logs on O(resource_ids) whose C(Name) tag equals this value are matched, replaced, or deleted.
        Other tags are not used for matching.
      - When O(state=present) and the flow log with this name has other settings, a new flow log with this name
        is created and the old one is deleted, and RV(deleted_flow_log_ids) lists it.
      - The new flow log is created before the old one is deleted, so logging continues.
      - The old flow log is kept, and the module fails, when its replacement is not active or reports failed
        delivery. It is also kept, with a warning, when EC2 does not yet return the new replacement; a later run
        deletes it.
      - Delivery failures that EC2 reports only after the first delivery attempt cannot be detected.
      - When O(state=present), the module fails before any change when more than one flow log with this name on
        a resource matches the requested settings. When O(state=absent), every flow log with this name that
        matches the specified attributes is deleted.
      - EC2 rejects a new flow log whose settings and destination equal those of another flow log on the same
        resource, so a flow log without this name that has the requested settings must be tagged with it or
        deleted first.
      - The value of O(name) overrides any value set for V(Name) in the O(tags) parameter.
      - When O(tags) is omitted, other tags are left unchanged; O(purge_tags) never removes the C(Name) tag set
        by this option.
      - A replacement flow log gets the tags of the flow log it replaces, changed by O(tags) and O(purge_tags) as
        they would change the tags of a kept flow log. Tags with the reserved C(aws:) prefix are not copied.
      - A replacement flow log also keeps the O(log_format) and O(max_aggregation_interval) of the flow log it
        replaces when these options are omitted, and its O(destination_options) when both flow logs deliver to
        S3. Each supplied option, including each O(destination_options) suboption, replaces only its own kept
        value.
      - A kept O(log_format) also keeps the tag field specifications that EC2 tag fields in that format require.
        A supplied O(log_format) is sent without them.
      - Keeping a log format with EC2 tag fields requires botocore 1.43.26 or later; with an older botocore, the
        replacement uses EC2's default format and the module warns.
      - This must not be empty or made only of spaces, tabs, carriage returns, and line feeds, because EC2 stores
        such a C(Name) tag as an empty value.
    required: true
    type: str
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
      - When O(state=absent), only O(name) and the other specified attributes are used to match flow logs.
      - O(tags) and O(purge_tags) are not used to match flow logs when O(state=absent); only O(name) selects flow
        logs by their C(Name) tag.
      - If only O(name) and O(resource_ids) are set, all flow logs with this name on those resources are removed.
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
    name: vpc-flow-logs

- name: Ensure subnet flow logs are delivered to S3
  linuxhq.aws.ec2_flow_log:
    name: subnet-flow-logs
    resource_ids:
      - subnet-0123456789abcdef0
    resource_type: Subnet
    log_destination_type: s3
    log_destination: arn:aws:s3:::example-flow-logs
    destination_options:
      file_format: parquet
      hive_compatible_partitions: true
      per_hour_partition: true

- name: Ensure the VPC flow log is absent
  linuxhq.aws.ec2_flow_log:
    name: vpc-flow-logs
    resource_ids:
      - vpc-0123456789abcdef0
    state: absent
"""

RETURN = r"""
deleted_flow_log_ids:
  description:
    - The EC2 flow log IDs with the O(name) and other settings that were replaced, or that would be replaced in
      check mode.
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
    name:
      description: The C(Name) tag of the flow log.
      returned: when the flow log has a C(Name) tag
      type: str
      version_added: "2.6.0"
    resource_id:
      description: ID of the monitored resource.
      returned: when available
      type: str
    tag_field_specifications:
      description: Tag configuration for EC2 tag fields in a custom log format.
      returned: when available
      type: list
      elements: dict
      contains:
        resource_type:
          description: Resource type of the tag keys used by the EC2 tag fields.
          returned: when available
          type: str
        tag_keys:
          description: Tag keys on the tagged resources displayed by the EC2 tag fields.
          returned: when available
          type: list
          elements: str
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

import json
import re
import uuid

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict, snake_dict_to_camel_dict

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
    EC2_BLANK_TAG_VALUE_CHARACTERS,
    apply_tag_deltas,
    ec2_tag_methods,
    reconcile_ec2_tags,
    require_no_reserved_tag_keys,
    require_resulting_tag_limit,
    require_valid_tags,
    updated_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.validation import require_non_blank

# The EC2 model documents 1000 IDs, but DeleteFlowLogs and DescribeFlowLogs return InternalError above 100.
MAX_FLOW_LOG_IDS_PER_REQUEST = 100
# EC2 rejects more resource IDs per CreateFlowLogs call.
MAX_RESOURCE_IDS_PER_CREATE = 300
MAX_TRANSIT_GATEWAY_RESOURCE_IDS_PER_CREATE = 25

# name matches the Name tag of a flow log.
ABSENT_MATCH_FIELDS = (
    "deliver_cross_account_role",
    "deliver_logs_permission_arn",
    "log_destination",
    "log_destination_type",
    "log_format",
    "log_group_name",
    "max_aggregation_interval",
    "name",
    "traffic_type",
)

PRESENT_MATCH_FIELDS = (
    "deliver_cross_account_role",
    "deliver_logs_permission_arn",
    "log_destination",
    "log_format",
    "log_group_name",
    "max_aggregation_interval",
    "name",
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

# EC2 tag fields of the flow log record format, which require TagFieldSpecifications.
TAG_FIELD_PATTERN = re.compile(r"\$\{(?:instance|interface|asg)-tag(?:-2)?\}")

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
    if "log_format" in desired:
        # EC2 stores a log format with each run of spaces and tabs between fields replaced by one space. It rejects
        # leading and trailing whitespace; such a run becomes one space here, which EC2 still rejects.
        desired["log_format"] = re.sub(r"[ \t]+", " ", desired["log_format"])

    destination_options = comparable_destination_options(module)
    if destination_options:
        desired["destination_options"] = destination_options

    return desired


def desired_tags(module):
    """Return the tags to converge on matching flow logs, with O(name) as the Name tag; None leaves tags unchanged."""
    tags = module.params["tags"]
    if tags is None:
        return None

    return dict(tags, Name=module.params["name"])


def replacement_settings(settings, replaced):
    """Return the create settings for a replacement, keeping the replaced flow log's settings the task omits."""
    kept = {}
    if isinstance(replaced.get("LogFormat"), str) and replaced["LogFormat"]:
        kept["log_format"] = replaced["LogFormat"]
        # EC2 rejects a format with EC2 tag fields without the tag field specifications that go with it.
        tag_field_specifications = replaced.get("TagFieldSpecifications")
        if "log_format" not in settings and isinstance(tag_field_specifications, list):
            tag_field_specifications = [
                camel_dict_to_snake_dict(specification)
                for specification in tag_field_specifications
                if isinstance(specification, dict)
            ]
            if tag_field_specifications:
                kept["tag_field_specifications"] = tag_field_specifications

        # botocore before 1.43.26 does not return the specifications, so EC2's default format is used instead.
        if "tag_field_specifications" not in kept and TAG_FIELD_PATTERN.search(kept["log_format"]):
            del kept["log_format"]

    if replaced.get("MaxAggregationInterval") in (60, 600):
        kept["max_aggregation_interval"] = replaced["MaxAggregationInterval"]

    effective = dict(kept, **settings)
    # Destination options apply only to S3, so they are kept only when both flow logs deliver to S3.
    if settings["log_destination_type"] == "s3" and replaced.get("LogDestinationType") == "s3":
        replaced_options = replaced.get("DestinationOptions")
        replaced_options = camel_dict_to_snake_dict(replaced_options if isinstance(replaced_options, dict) else {})
        destination_options = {
            key: value
            for key, value in replaced_options.items()
            if (key == "file_format" and value in ("plain-text", "parquet"))
            or (key in ("hive_compatible_partitions", "per_hour_partition") and isinstance(value, bool))
        }
        # Each supplied suboption replaces only its own kept value.
        destination_options.update(settings.get("destination_options", {}))
        if destination_options:
            effective["destination_options"] = destination_options

    return effective


def matching_flow_logs(module, flow_logs, desired):
    resource_ids = set(normalized_resource_ids(module))
    matching = []
    for flow_log in flow_logs:
        if not isinstance(flow_log, dict):
            module.fail_json(msg="AWS returned an invalid EC2 flow log")

        if flow_log.get("ResourceId") not in resource_ids:
            continue

        normalized = boto3_resource_to_ansible_dict(flow_log, transform_tags=False, force_tags=False)
        normalized["name"] = boto3_tag_list_to_ansible_dict(flow_log.get("Tags") or []).get("Name")
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


def verified_replacement(module, flow_logs, current, superseded_flow_log_ids, changed=False):
    """Return the flow logs that are safe to delete because their replacements are working.

    changed reports whether resources were already modified, for failure results.
    """
    superseded_resource_ids = {
        flow_log.get("ResourceId") for flow_log in flow_logs if flow_log.get("FlowLogId") in superseded_flow_log_ids
    }
    replacements = [flow_log for flow_log in current if flow_log.get("ResourceId") in superseded_resource_ids]
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
                f"superseded flow logs {', '.join(superseded_flow_log_ids)} were kept"
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
    if superseded_resource_ids - covered:
        module.warn(
            "EC2 has not returned the replacement flow logs yet; "
            f"superseded flow logs {', '.join(superseded_flow_log_ids)} were kept and will be purged on a later run"
        )
        return []

    return superseded_flow_log_ids


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
    name = module.params["name"]
    tags = desired_tags(module)
    desired = {
        "log_destination_type": module.params["log_destination_type"] or "cloud-watch-logs",
    }
    if resource_type in TRAFFIC_TYPE_RESOURCE_TYPES:
        desired["traffic_type"] = module.params["traffic_type"] or "ALL"

    desired.update(desired_match_fields(module, PRESENT_MATCH_FIELDS))
    flow_logs = get_flow_logs(client, module)
    current = matching_flow_logs(module, flow_logs, desired)
    for resource_id in resource_ids:
        count = sum(flow_log.get("ResourceId") == resource_id for flow_log in current)
        if count > 1:
            module.fail_json(
                msg=(
                    f"Found {count} EC2 flow logs named {name} on resource {resource_id} that match the requested "
                    "settings; delete all but one"
                )
            )

    # EC2 cannot modify a flow log, so a flow log with this name and other settings is replaced.
    matched_flow_log_ids = {flow_log["FlowLogId"] for flow_log in current}
    superseded_flow_logs = sorted(
        (
            flow_log
            for flow_log in matching_flow_logs(module, flow_logs, {"name": name})
            if flow_log["FlowLogId"] not in matched_flow_log_ids
        ),
        key=lambda flow_log: flow_log["FlowLogId"],
    )
    superseded_flow_log_ids = [flow_log["FlowLogId"] for flow_log in superseded_flow_logs]

    matched_resource_ids = {flow_log.get("ResourceId") for flow_log in current}
    missing_resource_ids = [resource_id for resource_id in resource_ids if resource_id not in matched_resource_ids]
    # name is sent as the Name tag, not as a flow log setting.
    create_settings = {key: value for key, value in desired.items() if key != "name"}
    created_settings = {}
    created_tags = {}
    dropped_format_flow_log_ids = []
    for resource_id in missing_resource_ids:
        # A replacement keeps the tags of the flow log it replaces, as a kept flow log would; EC2 rejects aws: keys.
        replaced_tags = {}
        replaced = {}
        created_settings[resource_id] = create_settings
        for flow_log in superseded_flow_logs:
            if flow_log.get("ResourceId") == resource_id:
                replaced = flow_log
                replaced_tags.update(boto3_tag_list_to_ansible_dict(flow_log.get("Tags") or []))
                # It also keeps the settings the task omits; as with tags, the last replaced flow log wins.
                created_settings[resource_id] = replacement_settings(create_settings, flow_log)

        replaced_format = replaced.get("LogFormat")
        if (
            isinstance(replaced_format, str)
            and TAG_FIELD_PATTERN.search(replaced_format)
            and "log_format" not in created_settings[resource_id]
        ):
            dropped_format_flow_log_ids.append(replaced["FlowLogId"])

        replaced_tags = {key: value for key, value in replaced_tags.items() if not key.lower().startswith("aws:")}
        if tags is None:
            created_tags[resource_id] = dict(replaced_tags, Name=name)
        else:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                replaced_tags, tags, purge_tags=module.params["purge_tags"]
            )
            require_resulting_tag_limit(module, replaced_tags, tags_to_set, tag_keys_to_unset, 50, "EC2 flow log")
            created_tags[resource_id] = updated_tags(replaced_tags, tags_to_set, tag_keys_to_unset)

    if dropped_format_flow_log_ids:
        module.warn(
            f"Replaced flow logs {', '.join(dropped_format_flow_log_ids)} use EC2 tag fields in their log format, "
            "which need botocore 1.43.26 or later to keep, so EC2's default format is used; set log_format to "
            "choose one"
        )

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
            # Live: EC2 rejects these keys, after any tag removal or flow log creation of the same run.
            require_no_reserved_tag_keys(module, tags_to_set)
            require_resulting_tag_limit(module, current_tags, tags_to_set, tag_keys_to_unset, 50, "EC2 flow log")

            if tags_to_set or tag_keys_to_unset:
                tags_changed.append((flow_log, tags_to_set, tag_keys_to_unset))

    changed = bool(missing_resource_ids or tags_changed or superseded_flow_log_ids)
    # Whether AWS was already modified, so failures after a mutation report changed=True.
    modified = False

    if changed and not module.check_mode:
        # Check every later operation first so an SDK gap fails before AWS is modified.
        later_methods = ec2_tag_methods(
            any(tags_to_set for _flow_log, tags_to_set, _tag_keys_to_unset in tags_changed),
            any(tag_keys_to_unset for _flow_log, _tags_to_set, tag_keys_to_unset in tags_changed),
        )

        if superseded_flow_log_ids:
            later_methods["delete_flow_logs"] = ("FlowLogIds",)

        require_client_methods(module, client, "EC2", later_methods)

    if missing_resource_ids:
        if not module.check_mode:
            # One request carries one set of settings and tags, so resources are grouped by those of their new flow log.
            groups = {}
            for resource_id in missing_resource_ids:
                base_request = snake_dict_to_camel_dict(
                    dict(created_settings[resource_id], resource_type=resource_type), capitalize_first=True
                )
                group_tags = tuple(sorted(created_tags[resource_id].items()))
                group_key = (json.dumps(base_request, sort_keys=True), group_tags)
                groups.setdefault(group_key, (base_request, group_tags, []))[2].append(resource_id)

            # Every flow log is created with at least its Name tag.
            create_parameters = dict.fromkeys(
                parameter for base_request, _tags, _ids in groups.values() for parameter in base_request
            )
            require_client_methods(
                module,
                client,
                "EC2",
                {"create_flow_logs": tuple(create_parameters) + ("ClientToken", "ResourceIds", "TagSpecifications")},
            )

            batch_size = MAX_RESOURCE_IDS_PER_CREATE
            if resource_type in TRANSIT_GATEWAY_RESOURCE_TYPES:
                batch_size = MAX_TRANSIT_GATEWAY_RESOURCE_IDS_PER_CREATE

            batches = [
                (base_request, group_tags, batch)
                for base_request, group_tags, group_resource_ids in groups.values()
                for batch in chunks(group_resource_ids, batch_size)
            ]
            created_flow_log_ids = []
            for base_request, group_tags, batch in batches:
                # One token per request makes SDK retries of a request that already succeeded idempotent.
                request = dict(
                    base_request,
                    ClientToken=str(uuid.uuid4()),
                    ResourceIds=batch,
                    TagSpecifications=boto3_tag_specifications(dict(group_tags), types="vpc-flow-log"),
                )

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
                    **created_settings[resource_id],
                )
                if desired["log_destination_type"] == "s3":
                    flow_log["destination_options"] = dict(
                        S3_DESTINATION_OPTION_DEFAULTS, **created_settings[resource_id].get("destination_options", {})
                    )

                flow_log = snake_dict_to_camel_dict(flow_log, capitalize_first=True)
                flow_log["Tags"] = ansible_dict_to_boto3_tag_list(created_tags[resource_id])

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
    if superseded_flow_log_ids:
        superseded_flow_log_ids = verified_replacement(
            module, flow_logs, current, superseded_flow_log_ids, changed=modified
        )
        if superseded_flow_log_ids and not module.check_mode:
            superseded_flow_log_ids = delete_flow_logs(client, module, superseded_flow_log_ids, changed=modified)
            modified = modified or bool(superseded_flow_log_ids)

    if not module.check_mode:
        # Report only work AWS performed, such as flow logs that were already gone when deleted.
        changed = modified

    flow_log_ids = [flow_log["FlowLogId"] for flow_log in current if flow_log.get("FlowLogId")]
    result_flow_logs = boto3_resource_list_to_ansible_dict(current, transform_tags=True, force_tags=False)
    for flow_log in result_flow_logs:
        if "Name" in (flow_log.get("tags") or {}):
            flow_log["name"] = flow_log["tags"]["Name"]

    module.exit_json(
        changed=changed,
        deleted_flow_log_ids=superseded_flow_log_ids,
        flow_log_ids=flow_log_ids,
        flow_logs=result_flow_logs,
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
        "name": {"required": True, "type": "str"},
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
        # matches them, and check mode would predict new flow logs.
        for option in (
            "deliver_cross_account_role",
            "deliver_logs_permission_arn",
            "log_destination",
            "log_format",
            "log_group_name",
        ):
            require_non_blank(module, module.params[option], option)

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

    name = module.params["name"]
    tags = module.params["tags"]
    # EC2 would store the Name tag as "", so the flow log could never be found by this name again.
    if not name.strip(EC2_BLANK_TAG_VALUE_CHARACTERS):
        module.fail_json(msg="name must not be empty")

    if state == "present":
        require_valid_tags(module, tags, 50, ec2=True)
        # name replaces any Name key in tags, and the Name tag counts toward the EC2 tag limit.
        require_valid_tags(module, dict(tags or {}, Name=name), 50, ec2=True)

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
