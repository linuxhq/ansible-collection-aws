#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: global_accelerator
short_description: Manage aws global accelerators
description:
  - Manages AWS Global Accelerator accelerators, their listeners, and their
    endpoint groups as one resource tree.
  - Listener entries in O(listeners) that exactly match an existing listener's
    protocol and port ranges keep that listener, remaining entries update
    existing listeners with the same protocol in place, and new listeners are
    created for the rest; existing listeners not present in O(listeners) are
    deleted when O(purge_listeners=true), including their endpoint groups.
  - Endpoint groups are identified by
    O(listeners[].endpoint_groups[].endpoint_group_region), which AWS keeps
    unique per listener, so entries update the existing endpoint group for
    their region in place before new endpoint groups are created; endpoint
    groups in regions not listed are deleted when O(purge_endpoint_groups=true).
  - When O(state=absent), endpoint groups, listeners, and the accelerator are
    removed in dependency order.
  - The Global Accelerator control plane uses the C(us-west-2) region.
author:
  - Taylor Kimball (@tkimball83)
options:
  arn:
    description:
      - ARN of the accelerator to manage.
      - O(arn) or O(name) is required.
      - When O(arn) is provided, the accelerator is managed directly instead of searching by O(name).
    aliases:
      - accelerator_arn
    type: str
  enabled:
    description:
      - Whether the accelerator is enabled.
    default: true
    type: bool
  idempotency_token:
    description:
      - Unique idempotency token for accelerator creation.
      - When omitted, a deterministic token is generated from O(name), O(ip_address_type), and O(ip_addresses).
      - This option is only used when creating an accelerator.
      - This must contain at most 255 characters.
    type: str
  ip_addresses:
    description:
      - Static IP addresses to assign to the accelerator.
      - These must be IP addresses from an AWS Global Accelerator BYOIP address pool.
      - This must contain at most 2 entries.
      - When omitted, AWS assigns IP addresses.
      - An empty list clears existing static IP addresses.
    elements: str
    type: list
  ip_address_type:
    description:
      - IP address type for the accelerator.
    choices:
      - DUAL_STACK
      - IPV4
    default: IPV4
    type: str
  listeners:
    description:
      - Listeners the accelerator should have.
      - Across all listeners, this must contain at most 42 endpoint groups.
      - When omitted, existing listeners are left unmanaged; an empty list
        removes all listeners when O(purge_listeners=true).
      - This option is ignored when O(state=absent).
    elements: dict
    suboptions:
      client_affinity:
        description:
          - Client affinity setting for the listener.
        choices:
          - NONE
          - SOURCE_IP
        default: NONE
        type: str
      endpoint_groups:
        description:
          - Endpoint groups the listener should have.
          - When omitted, existing endpoint groups are left unmanaged; an
            empty list removes all endpoint groups when
            O(purge_endpoint_groups=true).
        elements: dict
        suboptions:
          endpoint_configurations:
            description:
              - Endpoints for the endpoint group.
              - This must contain at most 10 entries.
              - When omitted, existing endpoints are left unmanaged; an empty
                list removes all endpoints from the endpoint group.
            elements: dict
            suboptions:
              attachment_arn:
                description:
                  - ARN of the cross-account attachment permitting the
                    endpoint.
                  - This requires botocore C(1.31.76) or later.
                type: str
              client_ip_preservation_enabled:
                description:
                  - Whether client IP address preservation is enabled for the
                    endpoint.
                  - When omitted, AWS applies the default for the endpoint
                    type.
                type: bool
              endpoint_id:
                description:
                  - ID of the endpoint, such as an EC2 instance ID, an elastic
                    IP allocation ID, or an Application or Network Load
                    Balancer ARN.
                required: true
                type: str
              weight:
                description:
                  - Weight for routing traffic to the endpoint.
                  - This must be between C(0) and C(255).
                default: 128
                type: int
            type: list
          endpoint_group_region:
            description:
              - AWS region of the endpoint group.
              - AWS allows one endpoint group per region for each listener,
                so this identifies the endpoint group.
              - This must contain at most 255 characters.
            required: true
            type: str
          health_check_interval_seconds:
            description:
              - Time in seconds between health checks for the endpoints.
              - When omitted, AWS applies its default.
            choices:
              - 10
              - 30
            type: int
          health_check_path:
            description:
              - Path for HTTP or HTTPS health checks.
              - This must start with C(/), contain only AWS-supported path
                characters, and contain at most 255 characters.
              - When omitted, AWS applies its default.
            type: str
          health_check_port:
            description:
              - Port used for endpoint health checks.
              - This must be between C(1) and C(65535).
              - When omitted, AWS uses the first port of the listener.
            type: int
          health_check_protocol:
            description:
              - Protocol used for endpoint health checks.
              - When omitted, AWS applies its default.
            choices:
              - HTTP
              - HTTPS
              - TCP
            type: str
          port_overrides:
            description:
              - Listener port to endpoint port overrides.
              - This must contain at most 10 entries.
              - When omitted, existing overrides are left unmanaged; an empty
                list removes all overrides from the endpoint group.
            elements: dict
            suboptions:
              endpoint_port:
                description:
                  - Endpoint port to receive the traffic.
                  - This must be between C(1) and C(65535).
                required: true
                type: int
              listener_port:
                description:
                  - Listener port to override.
                  - This must be between C(1) and C(65535).
                required: true
                type: int
            type: list
          threshold_count:
            description:
              - Number of consecutive health checks required to set an
                endpoint as healthy or unhealthy.
              - This must be between C(1) and C(10).
              - When omitted, AWS applies its default.
            type: int
          traffic_dial_percentage:
            description:
              - Percentage of traffic to send to the endpoint group.
              - This must be between C(0) and C(100).
              - When omitted, AWS applies its default.
            type: float
        type: list
      port_ranges:
        description:
          - Port ranges for the listener.
          - This list must contain at least one entry.
        elements: dict
        suboptions:
          from_port:
            description:
              - First port in the range.
              - This must be between C(1) and C(65535), and less than or equal
                to O(listeners[].port_ranges[].to_port).
            required: true
            type: int
          to_port:
            description:
              - Last port in the range.
              - This must be between C(1) and C(65535), and greater than or
                equal to O(listeners[].port_ranges[].from_port).
            required: true
            type: int
        required: true
        type: list
      protocol:
        description:
          - Protocol for the listener.
        choices:
          - TCP
          - UDP
        required: true
        type: str
    type: list
  name:
    description:
      - Name of the accelerator.
      - This is required when O(state=present).
      - O(arn) or O(name) is required.
      - This must contain at most 255 characters.
    type: str
  purge_endpoint_groups:
    description:
      - Whether existing endpoint groups in regions not listed in
        O(listeners[].endpoint_groups) should be removed from their listener.
      - This option is only applied to listeners with
        O(listeners[].endpoint_groups) provided.
    default: true
    type: bool
  purge_listeners:
    description:
      - Whether existing listeners not listed in O(listeners) should be
        removed from the accelerator, including their endpoint groups.
      - This option is only applied when O(listeners) is provided.
    default: true
    type: bool
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed from the accelerator.
      - This option is only applied when O(tags) is provided.
    default: true
    type: bool
  state:
    description:
      - Whether the accelerator should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the accelerator.
      - This must contain at most 50 entries; keys must contain 1 to 128 characters and values at most 256 characters.
    type: dict
  wait:
    description:
      - Whether to wait for the accelerator to finish deploying after changes
        are applied, and for disable and delete operations to complete when
        O(state=absent).
      - Accelerator, listener, and endpoint group changes are applied first
        and share a single deployment wait.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 10
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    default: 600
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a Global Accelerator accelerator is present
  linuxhq.aws.global_accelerator:
    name: example-accelerator
    enabled: true
    tags:
      Environment: production

- name: Ensure an accelerator with listeners and endpoint groups is present
  linuxhq.aws.global_accelerator:
    name: example-accelerator
    listeners:
      - protocol: TCP
        port_ranges:
          - from_port: 443
            to_port: 443
        endpoint_groups:
          - endpoint_group_region: us-east-1
            traffic_dial_percentage: 100
            endpoint_configurations:
              - endpoint_id: eipalloc-0123456789abcdef0
      - protocol: UDP
        port_ranges:
          - from_port: 53
            to_port: 53

- name: Ensure a Global Accelerator accelerator is absent
  linuxhq.aws.global_accelerator:
    name: example-accelerator
    state: absent
"""

RETURN = r"""
accelerator:
  description:
    - The accelerator.
    - Includes C(listeners) when O(listeners) is provided, and each listener
      includes C(endpoint_groups) when O(listeners[].endpoint_groups) is
      provided.
  returned: when an accelerator exists after module execution
  type: dict
accelerator_arn:
  description:
    - ARN of the accelerator.
  returned: when available
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import hashlib
import ipaddress
import json
import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    reconcile_arn_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
)

GLOBAL_ACCELERATOR_WAITER_MODEL_DATA = {
    "accelerator_deployed": {
        "delay": 10,
        "maxAttempts": 60,
        "operation": "DescribeAccelerator",
        "acceptors": [
            {
                "argument": "Accelerator.Status",
                "expected": "DEPLOYED",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "Accelerator.Status",
                "expected": "IN_PROGRESS",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
    "accelerator_deleted": {
        "delay": 10,
        "maxAttempts": 60,
        "operation": "DescribeAccelerator",
        "acceptors": [
            {
                "expected": "AcceleratorNotFoundException",
                "matcher": "error",
                "state": "success",
            },
            {
                "argument": "Accelerator.Status",
                "expected": "IN_PROGRESS",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}


def get_accelerator_by_arn(client, module, accelerator_arn):
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"describe_accelerator": ("AcceleratorArn",)},
    )
    try:
        return client.describe_accelerator(
            AcceleratorArn=accelerator_arn,
            aws_retry=True,
        ).get("Accelerator")
    except is_boto3_error_code("AcceleratorNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e, msg=f"Unable to describe AWS Global Accelerator {accelerator_arn}"
        )


def get_accelerator(client, module):
    if module.params["arn"] is not None:
        return get_accelerator_by_arn(client, module, module.params["arn"])

    name = module.params["name"]

    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"list_accelerators": ("MaxResults", "NextToken")},
    )
    accelerators = query_list(
        module,
        client,
        "list_accelerators",
        "Accelerators",
        "Unable to list AWS Global Accelerator accelerators",
    )

    matches = [
        accelerator for accelerator in accelerators if accelerator.get("Name") == name
    ]

    if len(matches) > 1:
        module.fail_json(
            msg=(
                "Multiple AWS Global Accelerator accelerators matched name "
                f"{name}; manage the accelerator by arn instead"
            )
        )

    if not matches:
        return None

    return matches[0]


def wait_for_accelerator(client, module, accelerator_arn, waiter_name):
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"describe_accelerator": ("AcceleratorArn",)},
    )
    run_waiter(
        module,
        client,
        GLOBAL_ACCELERATOR_WAITER_MODEL_DATA,
        waiter_name,
        f"Timed out waiting for AWS Global Accelerator {accelerator_arn}",
        AcceleratorArn=accelerator_arn,
    )


def normalized_port_ranges(port_ranges):
    return sorted(
        (
            {"from_port": item.get("from_port"), "to_port": item.get("to_port")}
            for item in port_ranges or []
        ),
        key=lambda item: (item["from_port"], item["to_port"]),
    )


def listener_identity(listener):
    return (
        listener["protocol"],
        tuple(
            (port_range["from_port"], port_range["to_port"])
            for port_range in listener["port_ranges"]
        ),
    )


def get_listeners(client, module, accelerator_arn):
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"list_listeners": ("AcceleratorArn", "MaxResults", "NextToken")},
    )
    listeners = query_list(
        module,
        client,
        "list_listeners",
        "Listeners",
        "Unable to list AWS Global Accelerator listeners for " f"{accelerator_arn}",
        AcceleratorArn=accelerator_arn,
    )

    normalized = []
    for listener in listeners:
        port_ranges = [
            {
                "from_port": port_range.get("FromPort"),
                "to_port": port_range.get("ToPort"),
            }
            for port_range in listener.get("PortRanges", [])
        ]

        normalized.append(
            {
                "client_affinity": listener.get("ClientAffinity", "NONE"),
                "listener_arn": listener.get("ListenerArn"),
                "port_ranges": normalized_port_ranges(port_ranges),
                "protocol": listener.get("Protocol"),
            }
        )

    return sorted(normalized, key=lambda item: item["listener_arn"])


def desired_listeners(module):
    desired_list = []
    for listener in module.params["listeners"]:
        desired = {
            "client_affinity": listener["client_affinity"],
            "endpoint_groups": listener["endpoint_groups"],
            "port_ranges": normalized_port_ranges(listener["port_ranges"]),
            "protocol": listener["protocol"],
        }
        desired_list.append(desired)

    return desired_list


def reconcile_listeners(module, current_listeners):
    remaining = list(current_listeners)
    matched, updates, creates = [], [], []

    pending = []
    for desired in desired_listeners(module):
        match = None
        for current in remaining:
            if listener_identity(current) == listener_identity(desired):
                match = current
                break

        if match is None:
            pending.append(desired)
            continue

        remaining.remove(match)
        if match["client_affinity"] != desired["client_affinity"]:
            updates.append((match, desired))
        else:
            matched.append((match, desired))

    for desired in pending:
        match = None
        for current in remaining:
            if current["protocol"] == desired["protocol"]:
                match = current
                break

        if match is None:
            creates.append(desired)
            continue

        remaining.remove(match)
        updates.append((match, desired))

    deletes = []
    if module.params["purge_listeners"]:
        deletes = remaining
    else:
        matched.extend((current, None) for current in remaining)

    return matched, updates, creates, deletes


def listener_request(desired):
    return snake_dict_to_camel_dict(
        {
            "client_affinity": desired["client_affinity"],
            "port_ranges": desired["port_ranges"],
            "protocol": desired["protocol"],
        },
        capitalize_first=True,
    )


def normalized_port_overrides(port_overrides):
    return sorted(
        (
            {
                "endpoint_port": item.get("endpoint_port"),
                "listener_port": item.get("listener_port"),
            }
            for item in port_overrides or []
        ),
        key=lambda item: (item["listener_port"], item["endpoint_port"]),
    )


def get_endpoint_groups(client, module, listener_arn):
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"list_endpoint_groups": ("ListenerArn", "MaxResults", "NextToken")},
    )
    endpoint_groups = query_list(
        module,
        client,
        "list_endpoint_groups",
        "EndpointGroups",
        "Unable to list AWS Global Accelerator endpoint groups for " f"{listener_arn}",
        ListenerArn=listener_arn,
    )

    normalized = [
        boto3_resource_to_ansible_dict(
            endpoint_group,
            transform_tags=False,
            force_tags=False,
        )
        for endpoint_group in endpoint_groups
    ]

    return sorted(normalized, key=lambda item: item["endpoint_group_region"])


def endpoint_group_requires_update(current, desired):
    for field in (
        "health_check_interval_seconds",
        "health_check_path",
        "health_check_port",
        "health_check_protocol",
        "threshold_count",
        "traffic_dial_percentage",
    ):
        if desired[field] is not None and desired[field] != current.get(field):
            return True

    if desired["port_overrides"] is not None:
        current_overrides = normalized_port_overrides(current.get("port_overrides"))

        if normalized_port_overrides(desired["port_overrides"]) != current_overrides:
            return True

    if desired["endpoint_configurations"] is not None:
        current_endpoints = {
            endpoint.get("endpoint_id"): endpoint
            for endpoint in current.get("endpoint_descriptions", [])
        }
        desired_ids = {
            configuration["endpoint_id"]
            for configuration in desired["endpoint_configurations"]
        }

        if desired_ids != set(current_endpoints):
            return True

        for configuration in desired["endpoint_configurations"]:
            endpoint = current_endpoints[configuration["endpoint_id"]]

            if configuration["weight"] != endpoint.get("weight"):
                return True

            if configuration[
                "client_ip_preservation_enabled"
            ] is not None and configuration[
                "client_ip_preservation_enabled"
            ] != endpoint.get(
                "client_ip_preservation_enabled"
            ):
                return True

            if configuration.get("attachment_arn") is not None and configuration.get(
                "attachment_arn"
            ) != endpoint.get("attachment_arn"):
                return True

    return False


def endpoint_group_request(desired):
    request = {}

    if desired["endpoint_configurations"] is not None:
        configurations = []
        for configuration in desired["endpoint_configurations"]:
            entry = {
                "EndpointId": configuration["endpoint_id"],
                "Weight": configuration["weight"],
            }
            if configuration["client_ip_preservation_enabled"] is not None:
                entry["ClientIPPreservationEnabled"] = configuration[
                    "client_ip_preservation_enabled"
                ]
            if configuration["attachment_arn"] is not None:
                entry["AttachmentArn"] = configuration["attachment_arn"]

            configurations.append(entry)

        request["EndpointConfigurations"] = configurations

    if desired["health_check_interval_seconds"] is not None:
        request["HealthCheckIntervalSeconds"] = desired["health_check_interval_seconds"]

    if desired["health_check_path"] is not None:
        request["HealthCheckPath"] = desired["health_check_path"]

    if desired["health_check_port"] is not None:
        request["HealthCheckPort"] = desired["health_check_port"]

    if desired["health_check_protocol"] is not None:
        request["HealthCheckProtocol"] = desired["health_check_protocol"]

    if desired["port_overrides"] is not None:
        request["PortOverrides"] = [
            {
                "EndpointPort": item["endpoint_port"],
                "ListenerPort": item["listener_port"],
            }
            for item in desired["port_overrides"]
        ]

    if desired["threshold_count"] is not None:
        request["ThresholdCount"] = desired["threshold_count"]

    if desired["traffic_dial_percentage"] is not None:
        request["TrafficDialPercentage"] = desired["traffic_dial_percentage"]

    return request


def require_endpoint_configuration_parameters(
    module, client, method_name, operation_name, request
):
    configurations = request.get("EndpointConfigurations")
    if not configurations:
        return

    available_parameters = (
        client.meta.service_model.operation_model(operation_name)
        .input_shape.members["EndpointConfigurations"]
        .member.members
    )
    requested_parameters = {
        parameter for configuration in configurations for parameter in configuration
    }
    for parameter_name in sorted(requested_parameters):
        if parameter_name not in available_parameters:
            module.fail_json(
                msg=(
                    "Installed botocore does not support Global Accelerator "
                    f"{method_name} EndpointConfigurations parameter "
                    f"{parameter_name}"
                )
            )


def predicted_endpoint_group(current, desired):
    predicted = dict(current or {})
    predicted["endpoint_group_region"] = desired["endpoint_group_region"]

    for field in (
        "health_check_interval_seconds",
        "health_check_path",
        "health_check_port",
        "health_check_protocol",
        "threshold_count",
        "traffic_dial_percentage",
    ):
        if desired[field] is not None:
            predicted[field] = desired[field]

    if desired["port_overrides"] is not None:
        predicted["port_overrides"] = normalized_port_overrides(
            desired["port_overrides"]
        )

    if desired["endpoint_configurations"] is not None:
        endpoint_descriptions = []
        for configuration in desired["endpoint_configurations"]:
            endpoint = {
                "endpoint_id": configuration["endpoint_id"],
                "weight": configuration["weight"],
            }
            if configuration["client_ip_preservation_enabled"] is not None:
                endpoint["client_ip_preservation_enabled"] = configuration[
                    "client_ip_preservation_enabled"
                ]
            if configuration.get("attachment_arn") is not None:
                endpoint["attachment_arn"] = configuration["attachment_arn"]

            endpoint_descriptions.append(endpoint)

        predicted["endpoint_descriptions"] = endpoint_descriptions

    return predicted


def delete_endpoint_group(client, module, endpoint_group_arn):
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"delete_endpoint_group": ("EndpointGroupArn",)},
    )
    try:
        client.delete_endpoint_group(
            EndpointGroupArn=endpoint_group_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("EndpointGroupNotFoundException"):
        return
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to delete AWS Global Accelerator endpoint group "
                f"{endpoint_group_arn}"
            ),
        )


def delete_listener(client, module, accelerator_arn, listener_arn):
    endpoint_groups = get_endpoint_groups(client, module, listener_arn)
    for endpoint_group in endpoint_groups:
        delete_endpoint_group(client, module, endpoint_group["endpoint_group_arn"])

    if endpoint_groups:
        wait_for_accelerator(client, module, accelerator_arn, "accelerator_deployed")

    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"delete_listener": ("ListenerArn",)},
    )
    try:
        client.delete_listener(
            ListenerArn=listener_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("ListenerNotFoundException"):
        return
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete AWS Global Accelerator listener {listener_arn}",
        )


def ensure_endpoint_groups(client, module, listener_arn, endpoint_groups):
    current_by_region = {}
    if listener_arn is not None:
        for endpoint_group in get_endpoint_groups(client, module, listener_arn):
            current_by_region[endpoint_group["endpoint_group_region"]] = endpoint_group

    changed = False
    results = []

    for desired in endpoint_groups:
        region = desired["endpoint_group_region"]

        current = current_by_region.pop(region, None)

        if current is None:
            changed = True
            if module.check_mode or listener_arn is None:
                results.append(predicted_endpoint_group(None, desired))
                continue

            token = hashlib.sha256(
                to_bytes(
                    json.dumps(
                        {
                            "endpoint_group_region": region,
                            "listener_arn": listener_arn,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            ).hexdigest()

            request = endpoint_group_request(desired)
            request["EndpointGroupRegion"] = region
            request["IdempotencyToken"] = token
            request["ListenerArn"] = listener_arn

            require_client_methods(
                module,
                client,
                "Global Accelerator",
                {"create_endpoint_group": tuple(request)},
            )
            require_endpoint_configuration_parameters(
                module,
                client,
                "create_endpoint_group",
                "CreateEndpointGroup",
                request,
            )
            try:
                endpoint_group = client.create_endpoint_group(
                    **request,
                    aws_retry=True,
                ).get("EndpointGroup")
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to create AWS Global Accelerator endpoint "
                        f"group {region} for {listener_arn}"
                    ),
                )

            if not (endpoint_group or {}).get("EndpointGroupArn"):
                module.fail_json(
                    msg=(
                        "AWS Global Accelerator did not return the created endpoint "
                        f"group {region} for {listener_arn}"
                    )
                )

            results.append(
                boto3_resource_to_ansible_dict(
                    endpoint_group,
                    transform_tags=False,
                    force_tags=False,
                )
            )
        elif endpoint_group_requires_update(current, desired):
            changed = True
            if module.check_mode:
                results.append(predicted_endpoint_group(current, desired))
                continue

            endpoint_group_arn = current["endpoint_group_arn"]
            request = endpoint_group_request(desired)
            request["EndpointGroupArn"] = endpoint_group_arn

            require_client_methods(
                module,
                client,
                "Global Accelerator",
                {"update_endpoint_group": tuple(request)},
            )
            require_endpoint_configuration_parameters(
                module,
                client,
                "update_endpoint_group",
                "UpdateEndpointGroup",
                request,
            )
            try:
                endpoint_group = client.update_endpoint_group(
                    **request,
                    aws_retry=True,
                ).get("EndpointGroup")
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to update AWS Global Accelerator endpoint "
                        f"group {endpoint_group_arn}"
                    ),
                )

            if not (endpoint_group or {}).get("EndpointGroupArn"):
                module.fail_json(
                    msg=(
                        "AWS Global Accelerator did not return the updated endpoint "
                        f"group {endpoint_group_arn}"
                    )
                )

            results.append(
                boto3_resource_to_ansible_dict(
                    endpoint_group,
                    transform_tags=False,
                    force_tags=False,
                )
            )
        else:
            results.append(current)

    remaining = list(current_by_region.values())
    if module.params["purge_endpoint_groups"]:
        if remaining:
            changed = True

        if not module.check_mode:
            for endpoint_group in remaining:
                delete_endpoint_group(
                    client, module, endpoint_group["endpoint_group_arn"]
                )
    else:
        results.extend(remaining)

    results = sorted(results, key=lambda item: item["endpoint_group_region"])
    return changed, results


def ensure_listeners(client, module, accelerator_arn):
    current_listeners = []
    if accelerator_arn is not None:
        current_listeners = get_listeners(client, module, accelerator_arn)

    matched, updates, creates, deletes = reconcile_listeners(module, current_listeners)
    changed = bool(updates or creates or deletes)
    result_listeners = []

    for current, desired in matched:
        result_listeners.append((dict(current), desired))

    for current, desired in updates:
        listener_arn = current["listener_arn"]
        result = {
            "client_affinity": desired["client_affinity"],
            "listener_arn": listener_arn,
            "port_ranges": desired["port_ranges"],
            "protocol": desired["protocol"],
        }
        result_listeners.append((result, desired))

        if module.check_mode:
            continue

        request = listener_request(desired)
        request["ListenerArn"] = listener_arn

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"update_listener": tuple(request)},
        )
        try:
            client.update_listener(
                **request,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to update AWS Global Accelerator listener "
                    f"{listener_arn}"
                ),
            )

    for desired in creates:
        result = {
            "client_affinity": desired["client_affinity"],
            "port_ranges": desired["port_ranges"],
            "protocol": desired["protocol"],
        }

        if module.check_mode or accelerator_arn is None:
            result_listeners.append((result, desired))
            continue

        token = hashlib.sha256(
            to_bytes(
                json.dumps(
                    {
                        "accelerator_arn": accelerator_arn,
                        "client_affinity": desired["client_affinity"],
                        "port_ranges": desired["port_ranges"],
                        "protocol": desired["protocol"],
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
        ).hexdigest()

        request = listener_request(desired)
        request["AcceleratorArn"] = accelerator_arn
        request["IdempotencyToken"] = token

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"create_listener": tuple(request)},
        )
        while True:
            try:
                listener = client.create_listener(
                    **request,
                    aws_retry=True,
                ).get("Listener")
                break
            except is_boto3_error_code("LimitExceededException") as e:
                if not deletes:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to create AWS Global Accelerator listener for "
                            f"{accelerator_arn}"
                        ),
                    )
                current = deletes.pop(0)
                delete_listener(
                    client, module, accelerator_arn, current["listener_arn"]
                )
                wait_for_accelerator(
                    client, module, accelerator_arn, "accelerator_deployed"
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to create AWS Global Accelerator listener for "
                        f"{accelerator_arn}"
                    ),
                )

        if not (listener or {}).get("ListenerArn"):
            module.fail_json(
                msg=(
                    "AWS Global Accelerator did not return the created listener for "
                    f"{accelerator_arn}"
                )
            )

        result["listener_arn"] = listener["ListenerArn"]
        result_listeners.append((result, desired))

    if not module.check_mode:
        for current in deletes:
            delete_listener(client, module, accelerator_arn, current["listener_arn"])

    if (
        changed
        and not module.check_mode
        and any(
            item[1] and item[1]["endpoint_groups"] is not None
            for item in result_listeners
        )
    ):
        wait_for_accelerator(client, module, accelerator_arn, "accelerator_deployed")

    results = []
    for result, desired in result_listeners:
        if desired is not None and desired["endpoint_groups"] is not None:
            endpoint_groups_changed, endpoint_groups = ensure_endpoint_groups(
                client,
                module,
                result.get("listener_arn"),
                desired["endpoint_groups"],
            )
            changed = changed or endpoint_groups_changed
            result["endpoint_groups"] = endpoint_groups

        results.append(result)

    results = sorted(results, key=listener_identity)
    return changed, results


def ensure_absent(client, module):
    accelerator = get_accelerator(client, module)
    changed = accelerator is not None

    if changed and not module.check_mode:
        accelerator_arn = accelerator["AcceleratorArn"]
        if accelerator.get("Status") and accelerator.get("Status") != "DEPLOYED":
            wait_for_accelerator(
                client, module, accelerator_arn, "accelerator_deployed"
            )
            accelerator = get_accelerator_by_arn(client, module, accelerator_arn)
            if accelerator is None:
                module.exit_json(changed=True, state="absent")
        listeners = get_listeners(client, module, accelerator_arn)

        for listener in listeners:
            delete_listener(client, module, accelerator_arn, listener["listener_arn"])

        if listeners:
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deployed",
            )

        if accelerator.get("Enabled"):
            require_client_methods(
                module,
                client,
                "Global Accelerator",
                {
                    "update_accelerator": (
                        "AcceleratorArn",
                        "Enabled",
                    )
                },
            )
            try:
                client.update_accelerator(
                    AcceleratorArn=accelerator_arn,
                    Enabled=False,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to disable AWS Global Accelerator " f"{accelerator_arn}"
                    ),
                )

            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deployed",
            )

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"delete_accelerator": ("AcceleratorArn",)},
        )
        try:
            client.delete_accelerator(
                AcceleratorArn=accelerator_arn,
                aws_retry=True,
            )
        except is_boto3_error_code("AcceleratorNotFoundException"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e, msg=f"Unable to delete AWS Global Accelerator {accelerator_arn}"
            )

        if module.params["wait"]:
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deleted",
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    tags = module.params["tags"]
    ip_addresses = module.params["ip_addresses"]
    desired = {
        "enabled": module.params["enabled"],
        "ip_address_type": module.params["ip_address_type"],
        "name": module.params["name"],
    }

    if ip_addresses is not None:
        desired["ip_addresses"] = sorted(ip_addresses)

    accelerator = get_accelerator(client, module)
    if accelerator is None and module.params.get("arn") is not None:
        module.fail_json(
            msg=f"AWS Global Accelerator {module.params['arn']} does not exist"
        )
    created = accelerator is None

    current_tags = {}
    if accelerator is not None and tags is not None:
        accelerator_arn = accelerator["AcceleratorArn"]

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"list_tags_for_resource": ("ResourceArn",)},
        )
        try:
            current_tags = boto3_tag_list_to_ansible_dict(
                client.list_tags_for_resource(
                    ResourceArn=accelerator_arn,
                    aws_retry=True,
                ).get("Tags", [])
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to list tags for AWS Global Accelerator "
                    f"{accelerator_arn}"
                ),
            )

    current = None
    if accelerator is not None:
        current = {
            "enabled": accelerator.get("Enabled"),
            "ip_address_type": accelerator.get("IpAddressType"),
            "name": accelerator.get("Name"),
        }

        if ip_addresses is not None:
            current_ip_addresses = []
            for ip_set in accelerator.get("IpSets", []):
                current_ip_addresses.extend(ip_set.get("IpAddresses", []))

            current["ip_addresses"] = sorted(current_ip_addresses)

    resource_changed = current != desired

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current_tags,
            tags,
            purge_tags=module.params["purge_tags"],
        )

    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if (
        accelerator is not None
        and not module.check_mode
        and (changed or module.params["listeners"] is not None)
        and accelerator.get("Status")
        and accelerator.get("Status") != "DEPLOYED"
    ):
        wait_for_accelerator(
            client,
            module,
            accelerator["AcceleratorArn"],
            "accelerator_deployed",
        )
        return ensure_present(client, module)

    if created and not module.check_mode:
        token = module.params["idempotency_token"]

        if token is None:
            token_fields = {
                "ip_address_type": desired["ip_address_type"],
                "name": desired["name"],
            }
            if "ip_addresses" in desired:
                token_fields["ip_addresses"] = desired["ip_addresses"]

            token = hashlib.sha256(
                to_bytes(
                    json.dumps(token_fields, separators=(",", ":"), sort_keys=True)
                )
            ).hexdigest()

        request = scrub_none_parameters(
            snake_dict_to_camel_dict(
                {
                    "enabled": desired["enabled"],
                    "idempotency_token": token,
                    "ip_addresses": ip_addresses,
                    "ip_address_type": desired["ip_address_type"],
                    "name": desired["name"],
                    "tags": (ansible_dict_to_boto3_tag_list(tags) if tags else None),
                },
                capitalize_first=True,
            )
        )

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"create_accelerator": tuple(request)},
        )
        try:
            accelerator = client.create_accelerator(
                **request,
                aws_retry=True,
            ).get("Accelerator")
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Global Accelerator {desired['name']}",
            )
        if not (accelerator or {}).get("AcceleratorArn"):
            module.fail_json(
                msg=(
                    "AWS Global Accelerator did not return the created accelerator "
                    f"{desired['name']}"
                )
            )
    elif created and module.check_mode:
        accelerator = {
            "Enabled": desired["enabled"],
            "IpAddressType": desired["ip_address_type"],
            "Name": desired["name"],
            "Status": "IN_PROGRESS",
        }
        if ip_addresses is not None:
            accelerator["IpSets"] = [{"IpAddresses": ip_addresses}]
    elif resource_changed and not module.check_mode:
        request = scrub_none_parameters(
            snake_dict_to_camel_dict(
                {
                    "accelerator_arn": accelerator["AcceleratorArn"],
                    "enabled": desired["enabled"],
                    "ip_addresses": ip_addresses,
                    "ip_address_type": desired["ip_address_type"],
                    "name": desired["name"],
                },
                capitalize_first=True,
            )
        )

        require_client_methods(
            module,
            client,
            "Global Accelerator",
            {"update_accelerator": tuple(request)},
        )
        try:
            accelerator = client.update_accelerator(
                **request,
                aws_retry=True,
            ).get("Accelerator")
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to update AWS Global Accelerator "
                    f"{request['AcceleratorArn']}"
                ),
            )
        if not (accelerator or {}).get("AcceleratorArn"):
            module.fail_json(
                msg=(
                    "AWS Global Accelerator did not return the updated accelerator "
                    f"{request['AcceleratorArn']}"
                )
            )
    elif resource_changed and module.check_mode:
        accelerator = dict(accelerator)
        accelerator["Enabled"] = desired["enabled"]
        accelerator["IpAddressType"] = desired["ip_address_type"]
        accelerator["Name"] = desired["name"]
        if ip_addresses is not None:
            accelerator["IpSets"] = [{"IpAddresses": ip_addresses}]

    listeners = None
    listeners_changed = False
    if module.params["listeners"] is not None:
        if created and module.params["listeners"] and not module.check_mode:
            wait_for_accelerator(
                client,
                module,
                accelerator["AcceleratorArn"],
                "accelerator_deployed",
            )
        listeners_changed, listeners = ensure_listeners(
            client,
            module,
            (accelerator or {}).get("AcceleratorArn"),
        )
        changed = changed or listeners_changed

    if (
        module.params["wait"]
        and not module.check_mode
        and (created or resource_changed or listeners_changed)
    ):
        accelerator_arn = (accelerator or {}).get("AcceleratorArn")

        if accelerator_arn:
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deployed",
            )
            accelerator = get_accelerator_by_arn(client, module, accelerator_arn)

    if accelerator is not None and tags is not None:
        if not created and not module.check_mode:
            accelerator_arn = accelerator["AcceleratorArn"]
            tag_methods = {}
            if tag_keys_to_unset:
                tag_methods["untag_resource"] = ("ResourceArn", "TagKeys")
            if tags_to_set:
                tag_methods["tag_resource"] = ("ResourceArn", "Tags")
            if tag_methods:
                require_client_methods(
                    module,
                    client,
                    "Global Accelerator",
                    tag_methods,
                )
            reconcile_arn_tags(
                module,
                client,
                accelerator_arn,
                tags_to_set,
                tag_keys_to_unset,
                "AWS Global Accelerator",
            )

        accelerator = dict(accelerator)

        for tag_key in tag_keys_to_unset:
            current_tags.pop(tag_key, None)

        current_tags.update(tags_to_set)
        accelerator["Tags"] = ansible_dict_to_boto3_tag_list(current_tags)

    result_accelerator = boto3_resource_to_ansible_dict(
        accelerator, transform_tags=True, force_tags=False
    )
    if listeners is not None:
        result_accelerator["listeners"] = listeners

    result = {
        "accelerator": result_accelerator,
        "changed": changed,
        "state": "present",
    }
    accelerator_arn = result_accelerator.get("accelerator_arn")

    if accelerator_arn is not None:
        result["accelerator_arn"] = accelerator_arn

    module.exit_json(**result)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "arn": {"aliases": ["accelerator_arn"], "type": "str"},
            "enabled": {"default": True, "type": "bool"},
            "idempotency_token": {"no_log": False, "type": "str"},
            "ip_addresses": {"elements": "str", "type": "list"},
            "ip_address_type": {
                "choices": ["DUAL_STACK", "IPV4"],
                "default": "IPV4",
                "type": "str",
            },
            "listeners": {
                "elements": "dict",
                "options": {
                    "client_affinity": {
                        "choices": ["NONE", "SOURCE_IP"],
                        "default": "NONE",
                        "type": "str",
                    },
                    "endpoint_groups": {
                        "elements": "dict",
                        "options": {
                            "endpoint_configurations": {
                                "elements": "dict",
                                "options": {
                                    "attachment_arn": {"type": "str"},
                                    "client_ip_preservation_enabled": {"type": "bool"},
                                    "endpoint_id": {
                                        "required": True,
                                        "type": "str",
                                    },
                                    "weight": {"default": 128, "type": "int"},
                                },
                                "type": "list",
                            },
                            "endpoint_group_region": {
                                "required": True,
                                "type": "str",
                            },
                            "health_check_interval_seconds": {
                                "choices": [10, 30],
                                "type": "int",
                            },
                            "health_check_path": {"type": "str"},
                            "health_check_port": {"type": "int"},
                            "health_check_protocol": {
                                "choices": ["HTTP", "HTTPS", "TCP"],
                                "type": "str",
                            },
                            "port_overrides": {
                                "elements": "dict",
                                "options": {
                                    "endpoint_port": {
                                        "required": True,
                                        "type": "int",
                                    },
                                    "listener_port": {
                                        "required": True,
                                        "type": "int",
                                    },
                                },
                                "type": "list",
                            },
                            "threshold_count": {"type": "int"},
                            "traffic_dial_percentage": {"type": "float"},
                        },
                        "type": "list",
                    },
                    "port_ranges": {
                        "elements": "dict",
                        "options": {
                            "from_port": {"required": True, "type": "int"},
                            "to_port": {"required": True, "type": "int"},
                        },
                        "required": True,
                        "type": "list",
                    },
                    "protocol": {
                        "choices": ["TCP", "UDP"],
                        "required": True,
                        "type": "str",
                    },
                },
                "type": "list",
            },
            "name": {"type": "str"},
            "purge_endpoint_groups": {"default": True, "type": "bool"},
            "purge_listeners": {"default": True, "type": "bool"},
            "purge_tags": {"default": True, "type": "bool"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "tags": {"type": "dict"},
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 10, "type": "int"},
            "wait_timeout": {"default": 600, "type": "int"},
        },
        required_if=[("state", "present", ["name"])],
        required_one_of=[["arn", "name"]],
        supports_check_mode=True,
    )

    state = module.params.get("state", "present")
    require_positive_wait_bounds(module, always=True)

    if len(module.params.get("name") or "") > 255:
        module.fail_json(msg="name must contain at most 255 characters")
    if state == "present" and len(module.params.get("idempotency_token") or "") > 255:
        module.fail_json(msg="idempotency_token must contain at most 255 characters")

    if state == "present" and len(module.params["ip_addresses"] or []) > 2:
        module.fail_json(msg="ip_addresses must contain at most 2 entries")
    if state == "present" and any(
        len(address) > 45 for address in module.params["ip_addresses"] or []
    ):
        module.fail_json(msg="ip_addresses entries must contain at most 45 characters")
    for address in module.params["ip_addresses"] or [] if state == "present" else []:
        try:
            ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError:
            module.fail_json(
                msg=f"ip_addresses entries must be valid IPv4 addresses: {address}"
            )
    if state == "present" and len(set(module.params["ip_addresses"] or [])) != len(
        module.params["ip_addresses"] or []
    ):
        module.fail_json(msg="ip_addresses entries must be unique")

    listener_identities = set()
    listener_port_ranges = {}
    if state == "present" and (
        sum(
            len(listener.get("endpoint_groups") or [])
            for listener in module.params["listeners"] or []
        )
        > 42
    ):
        module.fail_json(
            msg="listeners must contain at most 42 endpoint groups in total"
        )
    for listener in module.params["listeners"] or [] if state == "present" else []:
        if not listener["port_ranges"]:
            module.fail_json(
                msg="listeners entries require at least one port_ranges entry"
            )
        if len(listener["port_ranges"]) > 10:
            module.fail_json(
                msg="listeners entries allow at most 10 port_ranges entries"
            )

        for port_range in listener["port_ranges"]:
            if port_range["from_port"] < 1 or port_range["to_port"] > 65535:
                module.fail_json(msg="port_ranges entries must be between 1 and 65535")

            if port_range["from_port"] > port_range["to_port"]:
                module.fail_json(
                    msg=(
                        "port_ranges entries require from_port to be less "
                        "than or equal to to_port"
                    )
                )

        ordered_port_ranges = normalized_port_ranges(listener["port_ranges"])
        protocol_port_ranges = listener_port_ranges.setdefault(
            listener.get("protocol"), []
        )
        for port_range in ordered_port_ranges:
            if any(
                port_range["from_port"] <= current["to_port"]
                and current["from_port"] <= port_range["to_port"]
                for current in protocol_port_ranges
            ):
                module.fail_json(msg="listeners port_ranges entries must not overlap")
            protocol_port_ranges.append(port_range)

        identity = listener_identity(
            {
                "port_ranges": normalized_port_ranges(listener["port_ranges"]),
                "protocol": listener.get("protocol"),
            }
        )
        if identity in listener_identities:
            module.fail_json(
                msg=(
                    f"Duplicate listener with protocol {listener.get('protocol')} "
                    f"and port_ranges {normalized_port_ranges(listener['port_ranges'])} "
                    "in listeners"
                )
            )
        listener_identities.add(identity)

        regions = set()
        for endpoint_group in listener.get("endpoint_groups") or []:
            region = endpoint_group["endpoint_group_region"]

            if len(region) > 255:
                module.fail_json(
                    msg="endpoint_group_region must contain at most 255 characters"
                )

            if region in regions:
                module.fail_json(
                    msg=f"Duplicate endpoint group region {region} in endpoint_groups"
                )
            regions.add(region)

            if len(endpoint_group.get("endpoint_configurations") or []) > 10:
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} endpoint_configurations "
                        "must contain at most 10 entries"
                    )
                )

            if len(endpoint_group.get("port_overrides") or []) > 10:
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} port_overrides must contain "
                        "at most 10 entries"
                    )
                )

            if endpoint_group.get("health_check_port") is not None and not (
                1 <= endpoint_group["health_check_port"] <= 65535
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} health_check_port must be "
                        "between 1 and 65535"
                    )
                )

            health_check_path = endpoint_group.get("health_check_path")
            if health_check_path is not None and (
                len(health_check_path) > 255
                or re.fullmatch(r"/[-a-zA-Z0-9@:%_+.~#?&/=]*", health_check_path)
                is None
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} health_check_path must be a valid "
                        "path of at most 255 characters"
                    )
                )

            if endpoint_group.get("threshold_count") is not None and not (
                1 <= endpoint_group["threshold_count"] <= 10
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} threshold_count must be "
                        "between 1 and 10"
                    )
                )

            if endpoint_group.get("traffic_dial_percentage") is not None and not (
                0 <= endpoint_group["traffic_dial_percentage"] <= 100
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} traffic_dial_percentage "
                        "must be between 0 and 100"
                    )
                )

            endpoint_ids = set()
            for configuration in endpoint_group.get("endpoint_configurations") or []:
                endpoint_id = configuration["endpoint_id"]
                if (
                    len(endpoint_id) > 255
                    or len(configuration.get("attachment_arn") or "") > 255
                ):
                    module.fail_json(
                        msg=(
                            f"Endpoint group {region} endpoint IDs and attachment "
                            "ARNs must contain at most 255 characters"
                        )
                    )
                if endpoint_id in endpoint_ids:
                    module.fail_json(
                        msg=(
                            f"Duplicate endpoint {endpoint_id} in endpoint group "
                            f"{region} endpoint_configurations"
                        )
                    )
                endpoint_ids.add(endpoint_id)

                if not 0 <= configuration["weight"] <= 255:
                    module.fail_json(
                        msg=(
                            f"Endpoint group {region} endpoint_configurations "
                            "weight must be between 0 and 255"
                        )
                    )

            override_listener_ports = set()
            for port_override in endpoint_group.get("port_overrides") or []:
                if not (
                    1 <= port_override["listener_port"] <= 65535
                    and 1 <= port_override["endpoint_port"] <= 65535
                ):
                    module.fail_json(
                        msg=(
                            f"Endpoint group {region} port_overrides entries "
                            "must be between 1 and 65535"
                        )
                    )
                if port_override["listener_port"] in override_listener_ports:
                    module.fail_json(
                        msg=(
                            f"Endpoint group {region} port_overrides listener_port "
                            "values must be unique"
                        )
                    )
                override_listener_ports.add(port_override["listener_port"])

    require_valid_tags(
        module, module.params["tags"] if state == "present" else None, 50
    )
    client = module.client(
        "globalaccelerator",
        region="us-west-2",
        retry_decorator=AWSRetry.jittered_backoff(
            catch_extra_error_codes=["ConflictException"]
        ),
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
