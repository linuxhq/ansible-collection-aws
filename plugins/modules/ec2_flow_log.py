#!/usr/bin/python
# -*- coding: utf-8 -*-
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
  - Taylor Kimball
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
      - Requires O(log_destination_type).
      - O(log_destination_type) must be C(s3) when O(state=present).
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
    type: str
  log_group_name:
    description:
      - The CloudWatch Logs log group name for flow log data.
      - This is mutually exclusive with O(log_destination).
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
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)
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

OPTIONAL_CREATE_FLOW_LOG_PARAMETER_BY_OPTION = {
    "deliver_cross_account_role": "DeliverCrossAccountRole",
    "deliver_logs_permission_arn": "DeliverLogsPermissionArn",
    "log_destination": "LogDestination",
    "log_format": "LogFormat",
    "log_group_name": "LogGroupName",
    "max_aggregation_interval": "MaxAggregationInterval",
}

DESTINATION_OPTION_PARAMETER_BY_OPTION = {
    "file_format": "FileFormat",
    "hive_compatible_partitions": "HiveCompatiblePartitions",
    "per_hour_partition": "PerHourPartition",
}

PRESENT_MATCH_FIELDS = (
    "deliver_cross_account_role",
    "deliver_logs_permission_arn",
    "log_destination",
    "log_format",
    "log_group_name",
    "max_aggregation_interval",
)

TRAFFIC_TYPE_RESOURCE_TYPES = (
    "VPC",
    "Subnet",
    "NetworkInterface",
)

TRANSIT_GATEWAY_RESOURCE_TYPES = (
    "TransitGateway",
    "TransitGatewayAttachment",
)


def normalized_resource_ids(module):
    return list(dict.fromkeys(module.params["resource_ids"] or []))


def comparable_destination_options(module):
    return {
        key: value
        for key, value in (module.params["destination_options"] or {}).items()
        if value is not None
    }


def matching_flow_logs(module, flow_logs, desired):
    resource_ids = set(normalized_resource_ids(module))
    matching = []
    for flow_log in flow_logs:
        if flow_log.get("ResourceId") not in resource_ids:
            continue

        normalized = boto3_resource_to_ansible_dict(
            flow_log, transform_tags=False, force_tags=False
        )
        comparable = {}
        for key in desired:
            if key == "destination_options":
                current_destination_options = (
                    normalized.get("destination_options") or {}
                )
                destination_options = {}
                for option_key in desired["destination_options"]:
                    destination_options[option_key] = current_destination_options.get(
                        option_key
                    )

                comparable[key] = destination_options
            else:
                comparable[key] = normalized.get(key)

        if comparable != desired:
            continue

        matching.append(flow_log)

    return matching


def get_flow_logs(client, module):
    resource_ids = normalized_resource_ids(module)
    request = {
        "Filter": ansible_dict_to_boto3_filter_list({"resource-id": resource_ids})
    }

    try:
        return paginated_query_with_retries(
            client, "describe_flow_logs", **request
        ).get("FlowLogs", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to describe EC2 flow logs for resources "
                f"{', '.join(resource_ids)}"
            ),
        )


def ensure_absent(client, module):
    resource_ids = normalized_resource_ids(module)
    desired = {}
    for field in ABSENT_MATCH_FIELDS:
        if module.params[field] is not None:
            desired[field] = module.params[field]

    destination_options = comparable_destination_options(module)

    if destination_options:
        desired["destination_options"] = destination_options

    current = matching_flow_logs(module, get_flow_logs(client, module), desired)

    flow_log_ids = []
    for flow_log in current:
        if not flow_log.get("FlowLogId"):
            continue

        flow_log_ids.append(flow_log["FlowLogId"])

    changed = bool(flow_log_ids)

    if changed and not module.check_mode:
        try:
            response = client.delete_flow_logs(
                FlowLogIds=flow_log_ids,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to delete EC2 flow logs {', '.join(flow_log_ids)}"
            )

        unsuccessful = response.get("Unsuccessful", [])

        if unsuccessful:
            module.fail_json(
                msg="Unable to delete one or more EC2 flow logs",
                unsuccessful=boto3_resource_list_to_ansible_dict(
                    unsuccessful, transform_tags=False, force_tags=False
                ),
            )

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
        "log_destination_type": module.params["log_destination_type"]
        or "cloud-watch-logs",
    }
    if resource_type in TRAFFIC_TYPE_RESOURCE_TYPES:
        desired["traffic_type"] = module.params["traffic_type"] or "ALL"

    for field in PRESENT_MATCH_FIELDS:
        if module.params[field] is not None:
            desired[field] = module.params[field]

    destination_options = comparable_destination_options(module)

    if destination_options:
        desired["destination_options"] = destination_options

    current = matching_flow_logs(module, get_flow_logs(client, module), desired)

    matched_resource_ids = set()
    for flow_log in current:
        matched_resource_ids.add(flow_log.get("ResourceId"))

    missing_resource_ids = []
    for resource_id in resource_ids:
        if resource_id in matched_resource_ids:
            continue

        missing_resource_ids.append(resource_id)

    tags_changed = []
    if tags is not None:
        for flow_log in current:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(flow_log.get("Tags", [])),
                tags,
                purge_tags=module.params["purge_tags"],
            )

            if tags_to_set or tag_keys_to_unset:
                tags_changed.append((flow_log, tags_to_set, tag_keys_to_unset))

    changed = bool(missing_resource_ids or tags_changed)

    if changed:
        if missing_resource_ids and not module.check_mode:
            request = dict(
                desired,
                resource_ids=missing_resource_ids,
                resource_type=resource_type,
            )
            request = snake_dict_to_camel_dict(request, capitalize_first=True)

            if tags is not None:
                tag_specifications = boto3_tag_specifications(
                    tags, types="vpc-flow-log"
                )

                if tag_specifications is not None:
                    request["TagSpecifications"] = tag_specifications

            try:
                response = client.create_flow_logs(**request, aws_retry=True)
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to create EC2 flow logs for resources "
                        f"{', '.join(missing_resource_ids)}"
                    ),
                )

            unsuccessful = response.get("Unsuccessful", [])

            if unsuccessful:
                module.fail_json(
                    msg="Unable to create EC2 flow logs for one or more resources",
                    unsuccessful=boto3_resource_list_to_ansible_dict(
                        unsuccessful, transform_tags=False, force_tags=False
                    ),
                )

            created_flow_log_ids = response.get("FlowLogIds", [])

            if created_flow_log_ids:
                try:
                    created_flow_logs = paginated_query_with_retries(
                        client,
                        "describe_flow_logs",
                        FlowLogIds=created_flow_log_ids,
                    ).get("FlowLogs", [])
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to describe EC2 flow logs "
                            f"{', '.join(created_flow_log_ids)}"
                        ),
                    )

                current = current + created_flow_logs
        elif missing_resource_ids and module.check_mode:
            for resource_id in missing_resource_ids:
                flow_log = dict(
                    desired,
                    flow_log_status="ACTIVE",
                    resource_id=resource_id,
                    resource_type=resource_type,
                )
                flow_log = snake_dict_to_camel_dict(flow_log, capitalize_first=True)

                if tags is not None:
                    flow_log["Tags"] = ansible_dict_to_boto3_tag_list(tags)

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
                try:
                    client.delete_tags(
                        Resources=delete_resources,
                        Tags=[{"Key": key} for key in tag_keys_to_unset],
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to remove tags from EC2 flow logs "
                            f"{', '.join(delete_resources)}"
                        ),
                    )

            for tags_to_set, create_resources in create_groups.items():
                try:
                    client.create_tags(
                        Resources=create_resources,
                        Tags=ansible_dict_to_boto3_tag_list(dict(tags_to_set)),
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to tag EC2 flow logs "
                            f"{', '.join(create_resources)}"
                        ),
                    )

        for flow_log, tags_to_set, tag_keys_to_unset in tags_changed:
            current_tags = boto3_tag_list_to_ansible_dict(flow_log.get("Tags", []))

            for tag_key in tag_keys_to_unset:
                current_tags.pop(tag_key, None)

            current_tags.update(tags_to_set)
            flow_log["Tags"] = ansible_dict_to_boto3_tag_list(current_tags)

    flow_log_ids = []
    for flow_log in current:
        if not flow_log.get("FlowLogId"):
            continue

        flow_log_ids.append(flow_log["FlowLogId"])

    module.exit_json(
        changed=changed,
        flow_log_ids=flow_log_ids,
        flow_logs=boto3_resource_list_to_ansible_dict(
            current, transform_tags=True, force_tags=False
        ),
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
        mutually_exclusive=[["log_destination", "log_group_name"]],
        required_by={"destination_options": ["log_destination_type"]},
        required_if=[("state", "present", ["resource_type"])],
        supports_check_mode=True,
    )
    state = module.params["state"]
    resource_ids = normalized_resource_ids(module)
    resource_type = module.params["resource_type"]
    tags = module.params["tags"]
    destination_options = comparable_destination_options(module)

    if not resource_ids:
        module.fail_json(msg="resource_ids must contain at least one item")
    if (
        state == "present"
        and module.params["traffic_type"] is not None
        and resource_type in TRANSIT_GATEWAY_RESOURCE_TYPES
    ):
        module.fail_json(
            msg=(
                "traffic_type is not supported when resource_type is "
                "TransitGateway or TransitGatewayAttachment"
            )
        )
    if (
        state == "present"
        and destination_options
        and module.params["log_destination_type"] != "s3"
    ):
        module.fail_json(
            msg=(
                "destination_options requires log_destination_type to be s3 "
                "when state is present"
            )
        )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())
    method_names = ["describe_flow_logs"]
    if state == "present":
        method_names.append("create_flow_logs")
        if tags is not None:
            method_names.append("create_tags")
            if module.params["purge_tags"]:
                method_names.append("delete_tags")
    elif state == "absent":
        method_names.append("delete_flow_logs")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in method_names:
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support EC2 {method_name}"
            )

    if state == "present":
        create_flow_logs_parameters = method_parameters["create_flow_logs"]
        required_create_parameters = [
            "LogDestinationType",
            "ResourceIds",
            "ResourceType",
        ]
        if resource_type in TRAFFIC_TYPE_RESOURCE_TYPES:
            required_create_parameters.append("TrafficType")
        if tags is not None:
            required_create_parameters.append("TagSpecifications")

        for (
            option_name,
            parameter_name,
        ) in OPTIONAL_CREATE_FLOW_LOG_PARAMETER_BY_OPTION.items():
            if module.params[option_name] is None:
                continue

            required_create_parameters.append(parameter_name)

        if destination_options:
            required_create_parameters.append("DestinationOptions")

        for parameter_name in required_create_parameters:
            if parameter_name in create_flow_logs_parameters:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support EC2 "
                    f"create_flow_logs parameter {parameter_name}"
                )
            )

        if destination_options and "DestinationOptions" in create_flow_logs_parameters:
            destination_option_parameters = (
                client.meta.service_model.operation_model("CreateFlowLogs")
                .input_shape.members["DestinationOptions"]
                .members
            )

            for (
                option_name,
                parameter_name,
            ) in DESTINATION_OPTION_PARAMETER_BY_OPTION.items():
                if option_name not in destination_options:
                    continue

                if parameter_name in destination_option_parameters:
                    continue

                module.fail_json(
                    msg=(
                        "Installed botocore does not support EC2 "
                        "create_flow_logs DestinationOptions parameter "
                        f"{parameter_name}"
                    )
                )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
