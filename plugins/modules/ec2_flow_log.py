#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_flow_log
short_description: Manage aws ec2 flow logs
description:
  - Creates and deletes EC2 flow logs for VPC, subnet, network interface,
    and transit gateway resources.
  - Manages tags on existing matching flow logs.
author:
  - Taylor Kimball (@tkimball83)
options:
  deliver_cross_account_role:
    description:
      - The ARN of the IAM role that permits delivery to a cross-account destination.
    type: str
  deliver_logs_permission_arn:
    description:
      - The ARN of the IAM role that permits delivery to CloudWatch Logs.
    type: str
  destination_options:
    description:
      - Destination options for flow logs delivered to Amazon S3.
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
    type: str
  log_group_name:
    description:
      - The CloudWatch Logs log group name for flow log data.
    type: str
  max_aggregation_interval:
    description:
      - The maximum interval, in seconds, during which packets are captured and aggregated.
    type: int
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  resource_ids:
    description:
      - The IDs of the resources for which flow logs are managed.
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
    required: true
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
  tags:
    description:
      - Tags to apply to the flow logs.
    type: dict
  traffic_type:
    description:
      - The type of traffic to log.
      - This is only supported when O(resource_type) is C(VPC), C(Subnet), or C(NetworkInterface).
      - Defaults to C(ALL) when O(state=present) and O(resource_type) supports traffic type.
    choices:
      - ACCEPT
      - REJECT
      - ALL
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
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
flow_log_ids:
  description:
    - The matching EC2 flow log IDs.
  returned: always
  type: list
  elements: str
flow_logs:
  description:
    - The matching EC2 flow logs after module execution.
  returned: when O(state=present)
  type: list
  elements: dict
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

from ansible.module_utils.common.dict_transformations import (
    recursive_diff,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def normalized_resource_ids(module):
    return list(dict.fromkeys(module.params["resource_ids"] or []))


def comparable_destination_options(destination_options):
    return {
        key: value
        for key, value in (destination_options or {}).items()
        if value is not None
    }


def desired_present_flow_log(module):
    desired = {
        "log_destination_type": module.params["log_destination_type"]
        or "cloud-watch-logs",
    }
    if module.params["resource_type"] not in (
        "TransitGateway",
        "TransitGatewayAttachment",
    ):
        desired["traffic_type"] = module.params["traffic_type"] or "ALL"

    for field in (
        "deliver_cross_account_role",
        "deliver_logs_permission_arn",
        "log_destination",
        "log_format",
        "log_group_name",
        "max_aggregation_interval",
    ):
        if module.params[field] is not None:
            desired[field] = module.params[field]

    destination_options = comparable_destination_options(
        module.params["destination_options"]
    )
    if destination_options:
        desired["destination_options"] = destination_options
    return desired


def desired_absent_flow_log(module):
    desired = {}
    for field in (
        "deliver_cross_account_role",
        "deliver_logs_permission_arn",
        "log_destination",
        "log_destination_type",
        "log_format",
        "log_group_name",
        "max_aggregation_interval",
        "traffic_type",
    ):
        if module.params[field] is not None:
            desired[field] = module.params[field]

    destination_options = comparable_destination_options(
        module.params["destination_options"]
    )
    if destination_options:
        desired["destination_options"] = destination_options
    return desired


def comparable_flow_log(flow_log, desired):
    normalized = boto3_resource_to_ansible_dict(
        flow_log or {}, transform_tags=False, force_tags=False
    )
    comparable = {}
    for key in desired:
        if key == "destination_options":
            comparable[key] = {
                option_key: (normalized.get("destination_options") or {}).get(
                    option_key
                )
                for option_key in desired["destination_options"]
            }
        else:
            comparable[key] = normalized.get(key)
    return comparable


def flow_log_matches(flow_log, desired):
    return recursive_diff(comparable_flow_log(flow_log, desired), desired) is None


def matching_flow_logs(module, flow_logs, desired):
    resource_ids = set(normalized_resource_ids(module))
    return [
        flow_log
        for flow_log in flow_logs
        if flow_log.get("ResourceId") in resource_ids
        and flow_log_matches(flow_log, desired)
    ]


def get_flow_logs(client, module):
    request = {
        "Filter": ansible_dict_to_boto3_filter_list(
            {"resource-id": normalized_resource_ids(module)}
        )
    }
    try:
        return paginated_query_with_retries(
            client, "describe_flow_logs", **request
        ).get("FlowLogs", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 flow logs")


def flow_logs_by_ids(client, module, flow_log_ids):
    if not flow_log_ids:
        return []
    try:
        return paginated_query_with_retries(
            client,
            "describe_flow_logs",
            FlowLogIds=flow_log_ids,
        ).get("FlowLogs", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 flow logs")


def create_flow_logs(client, module, resource_ids):
    request = dict(
        desired_present_flow_log(module),
        resource_ids=resource_ids,
        resource_type=module.params["resource_type"],
    )
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(request, capitalize_first=True)
    )
    if module.params["tags"] is not None:
        request["TagSpecifications"] = [
            {
                "ResourceType": "vpc-flow-log",
                "Tags": ansible_dict_to_boto3_tag_list(module.params["tags"]),
            }
        ]

    try:
        response = client.create_flow_logs(**request, aws_retry=True)
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to create EC2 flow logs")

    unsuccessful = response.get("Unsuccessful", [])
    if unsuccessful:
        module.fail_json(
            msg="Unable to create EC2 flow logs for one or more resources",
            unsuccessful=boto3_resource_list_to_ansible_dict(
                unsuccessful, transform_tags=False, force_tags=False
            ),
        )
    return response.get("FlowLogIds", [])


def delete_flow_logs(client, module, flow_log_ids):
    try:
        response = client.delete_flow_logs(
            FlowLogIds=flow_log_ids,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to delete EC2 flow logs")

    unsuccessful = response.get("Unsuccessful", [])
    if unsuccessful:
        module.fail_json(
            msg="Unable to delete one or more EC2 flow logs",
            unsuccessful=boto3_resource_list_to_ansible_dict(
                unsuccessful, transform_tags=False, force_tags=False
            ),
        )


def apply_tag_changes(client, module, flow_log_id, tags_to_set, tag_keys_to_unset):
    if tag_keys_to_unset:
        try:
            client.delete_tags(
                Resources=[flow_log_id],
                Tags=[{"Key": key} for key in tag_keys_to_unset],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to remove tags from EC2 flow log {flow_log_id}"
            )

    if tags_to_set:
        try:
            client.create_tags(
                Resources=[flow_log_id],
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(e, msg=f"Unable to tag EC2 flow log {flow_log_id}")


def with_check_mode_tags(module, flow_log):
    if module.params["tags"] is None:
        return flow_log
    flow_log = dict(flow_log or {})
    current_tags = boto3_tag_list_to_ansible_dict(flow_log.get("Tags", []))
    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        current_tags,
        module.params["tags"],
        purge_tags=module.params["purge_tags"],
    )
    for tag_key in tag_keys_to_unset:
        current_tags.pop(tag_key, None)
    current_tags.update(tags_to_set)
    flow_log["Tags"] = ansible_dict_to_boto3_tag_list(current_tags)
    return flow_log


def check_mode_flow_log(module, resource_id):
    flow_log = dict(
        desired_present_flow_log(module),
        flow_log_status="ACTIVE",
        resource_id=resource_id,
        resource_type=module.params["resource_type"],
    )
    flow_log = snake_dict_to_camel_dict(flow_log, capitalize_first=True)
    if module.params["tags"] is not None:
        flow_log["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
    return flow_log


def normalize_flow_logs(flow_logs):
    return boto3_resource_list_to_ansible_dict(
        flow_logs or [], transform_tags=True, force_tags=False
    )


def ensure_absent(client, module):
    desired = desired_absent_flow_log(module)
    current = matching_flow_logs(module, get_flow_logs(client, module), desired)
    flow_log_ids = [
        flow_log["FlowLogId"] for flow_log in current if flow_log.get("FlowLogId")
    ]
    changed = bool(flow_log_ids)

    if changed and not module.check_mode:
        delete_flow_logs(client, module, flow_log_ids)

    module.exit_json(
        changed=changed,
        flow_log_ids=flow_log_ids,
        resource_ids=normalized_resource_ids(module),
        state="absent",
    )


def ensure_present(client, module):
    desired = desired_present_flow_log(module)
    current = matching_flow_logs(module, get_flow_logs(client, module), desired)
    matched_resource_ids = {flow_log.get("ResourceId") for flow_log in current}
    missing_resource_ids = [
        resource_id
        for resource_id in normalized_resource_ids(module)
        if resource_id not in matched_resource_ids
    ]

    tags_changed = []
    for flow_log in current:
        tags_to_set, tag_keys_to_unset = ({}, [])
        if module.params["tags"] is not None:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict((flow_log or {}).get("Tags", [])),
                module.params["tags"],
                purge_tags=module.params["purge_tags"],
            )
        if tags_to_set or tag_keys_to_unset:
            tags_changed.append((flow_log, tags_to_set, tag_keys_to_unset))

    changed = bool(missing_resource_ids or tags_changed)

    if changed and not module.check_mode:
        created_flow_log_ids = []
        if missing_resource_ids:
            created_flow_log_ids = create_flow_logs(
                client, module, missing_resource_ids
            )
        if created_flow_log_ids:
            current = current + flow_logs_by_ids(client, module, created_flow_log_ids)

        for flow_log, tags_to_set, tag_keys_to_unset in tags_changed:
            apply_tag_changes(
                client,
                module,
                flow_log["FlowLogId"],
                tags_to_set,
                tag_keys_to_unset,
            )
        current = matching_flow_logs(module, get_flow_logs(client, module), desired)
    elif changed and module.check_mode:
        current = [with_check_mode_tags(module, flow_log) for flow_log in current] + [
            check_mode_flow_log(module, resource_id)
            for resource_id in missing_resource_ids
        ]

    flow_log_ids = [
        flow_log["FlowLogId"] for flow_log in current if flow_log.get("FlowLogId")
    ]
    module.exit_json(
        changed=changed,
        flow_log_ids=flow_log_ids,
        flow_logs=normalize_flow_logs(current),
        resource_ids=normalized_resource_ids(module),
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
        "max_aggregation_interval": {"type": "int"},
        "purge_tags": {"default": True, "type": "bool"},
        "resource_ids": {"elements": "str", "required": True, "type": "list"},
        "resource_type": {
            "choices": [
                "VPC",
                "Subnet",
                "NetworkInterface",
                "TransitGateway",
                "TransitGatewayAttachment",
            ],
            "type": "str",
        },
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"type": "dict"},
        "traffic_type": {"choices": ["ACCEPT", "REJECT", "ALL"], "type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["resource_type"])],
        supports_check_mode=True,
    )
    if not normalized_resource_ids(module):
        module.fail_json(msg="resource_ids must contain at least one item")
    if (
        module.params["state"] == "present"
        and module.params["traffic_type"] is not None
        and module.params["resource_type"]
        in ("TransitGateway", "TransitGatewayAttachment")
    ):
        module.fail_json(
            msg=(
                "traffic_type is not supported when resource_type is "
                "TransitGateway or TransitGatewayAttachment"
            )
        )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
