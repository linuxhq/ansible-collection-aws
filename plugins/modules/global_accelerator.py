#!/usr/bin/python
# -*- coding: utf-8 -*-
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
    type: str
  ip_addresses:
    description:
      - Static IP addresses to assign to the accelerator.
      - These must be IP addresses from an AWS Global Accelerator BYOIP address pool.
      - When omitted, AWS assigns IP addresses.
      - An empty list is treated the same as omitting this option.
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
              - When omitted, existing endpoints are left unmanaged; an empty
                list removes all endpoints from the endpoint group.
            elements: dict
            suboptions:
              attachment_arn:
                description:
                  - ARN of the cross-account attachment permitting the
                    endpoint.
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
import json

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    build_waiter_factory,
    require_positive_wait_bounds,
)
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    custom_waiter_config,
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
    try:
        return client.describe_accelerator(
            AcceleratorArn=accelerator_arn,
            aws_retry=True,
        ).get("Accelerator")
    except is_boto3_error_code("AcceleratorNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to describe AWS Global Accelerator {accelerator_arn}"
        )


def get_accelerator(client, module):
    if module.params["arn"] is not None:
        return get_accelerator_by_arn(client, module, module.params["arn"])

    name = module.params["name"]

    try:
        accelerators = paginated_query_with_retries(
            client,
            "list_accelerators",
        ).get("Accelerators", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to list AWS Global Accelerator accelerators"
        )

    matches = []
    for accelerator in accelerators:
        if accelerator.get("Name") == name:
            matches.append(accelerator)

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
    try:
        waiter = build_waiter_factory(GLOBAL_ACCELERATOR_WAITER_MODEL_DATA).get_waiter(
            client, waiter_name
        )
        waiter.wait(
            AcceleratorArn=accelerator_arn,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=module.params["wait_delay"],
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Timed out waiting for AWS Global Accelerator {accelerator_arn}",
        )


def normalized_port_ranges(port_ranges):
    normalized = []
    for port_range in port_ranges or []:
        normalized.append(
            {
                "from_port": port_range.get("from_port"),
                "to_port": port_range.get("to_port"),
            }
        )

    return sorted(normalized, key=lambda item: (item["from_port"], item["to_port"]))


def listener_identity(listener):
    return (
        listener["protocol"],
        tuple(
            (port_range["from_port"], port_range["to_port"])
            for port_range in listener["port_ranges"]
        ),
    )


def get_listeners(client, module, accelerator_arn):
    try:
        listeners = paginated_query_with_retries(
            client,
            "list_listeners",
            AcceleratorArn=accelerator_arn,
        ).get("Listeners", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list AWS Global Accelerator listeners for "
                f"{accelerator_arn}"
            ),
        )

    normalized = []
    for listener in listeners:
        port_ranges = []
        for port_range in listener.get("PortRanges", []):
            port_ranges.append(
                {
                    "from_port": port_range.get("FromPort"),
                    "to_port": port_range.get("ToPort"),
                }
            )

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
    identities = set()
    for listener in module.params["listeners"]:
        desired = {
            "client_affinity": listener["client_affinity"],
            "endpoint_groups": listener["endpoint_groups"],
            "port_ranges": normalized_port_ranges(listener["port_ranges"]),
            "protocol": listener["protocol"],
        }

        identity = listener_identity(desired)

        if identity in identities:
            module.fail_json(
                msg=(
                    f"Duplicate listener with protocol {desired['protocol']} "
                    f"and port_ranges {desired['port_ranges']} in listeners"
                )
            )

        identities.add(identity)
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
        for current in remaining:
            matched.append((current, None))

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
    normalized = []
    for port_override in port_overrides or []:
        normalized.append(
            {
                "endpoint_port": port_override.get("endpoint_port"),
                "listener_port": port_override.get("listener_port"),
            }
        )

    return sorted(
        normalized, key=lambda item: (item["listener_port"], item["endpoint_port"])
    )


def get_endpoint_groups(client, module, listener_arn):
    try:
        endpoint_groups = paginated_query_with_retries(
            client,
            "list_endpoint_groups",
            ListenerArn=listener_arn,
        ).get("EndpointGroups", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list AWS Global Accelerator endpoint groups for "
                f"{listener_arn}"
            ),
        )

    normalized = []
    for endpoint_group in endpoint_groups:
        normalized.append(
            boto3_resource_to_ansible_dict(
                endpoint_group,
                transform_tags=False,
                force_tags=False,
            )
        )

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
        current_endpoints = {}
        for endpoint in current.get("endpoint_descriptions", []):
            current_endpoints[endpoint.get("endpoint_id")] = endpoint

        desired_ids = set()
        for configuration in desired["endpoint_configurations"]:
            desired_ids.add(configuration["endpoint_id"])

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
        port_overrides = []
        for port_override in desired["port_overrides"]:
            port_overrides.append(
                {
                    "EndpointPort": port_override["endpoint_port"],
                    "ListenerPort": port_override["listener_port"],
                }
            )

        request["PortOverrides"] = port_overrides

    if desired["threshold_count"] is not None:
        request["ThresholdCount"] = desired["threshold_count"]

    if desired["traffic_dial_percentage"] is not None:
        request["TrafficDialPercentage"] = desired["traffic_dial_percentage"]

    return request


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

            endpoint_descriptions.append(endpoint)

        predicted["endpoint_descriptions"] = endpoint_descriptions

    return predicted


def delete_endpoint_group(client, module, endpoint_group_arn):
    try:
        client.delete_endpoint_group(
            EndpointGroupArn=endpoint_group_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("EndpointGroupNotFoundException"):
        return
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to delete AWS Global Accelerator endpoint group "
                f"{endpoint_group_arn}"
            ),
        )


def delete_listener(client, module, listener_arn):
    for endpoint_group in get_endpoint_groups(client, module, listener_arn):
        delete_endpoint_group(client, module, endpoint_group["endpoint_group_arn"])

    try:
        client.delete_listener(
            ListenerArn=listener_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("ListenerNotFoundException"):
        return
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete AWS Global Accelerator listener {listener_arn}",
        )


def ensure_endpoint_groups(client, module, listener_arn, endpoint_groups):
    regions = set()
    for endpoint_group in endpoint_groups:
        region = endpoint_group["endpoint_group_region"]

        if region in regions:
            module.fail_json(
                msg=("Duplicate endpoint group region " f"{region} in endpoint_groups")
            )

        regions.add(region)

        endpoint_ids = set()
        for configuration in endpoint_group["endpoint_configurations"] or []:
            endpoint_id = configuration["endpoint_id"]

            if endpoint_id in endpoint_ids:
                module.fail_json(
                    msg=(
                        f"Duplicate endpoint {endpoint_id} in endpoint group "
                        f"{region} endpoint_configurations"
                    )
                )

            endpoint_ids.add(endpoint_id)

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

            try:
                endpoint_group = client.create_endpoint_group(
                    **request,
                    aws_retry=True,
                ).get("EndpointGroup")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to create AWS Global Accelerator endpoint "
                        f"group {region} for {listener_arn}"
                    ),
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

            try:
                endpoint_group = client.update_endpoint_group(
                    **request,
                    aws_retry=True,
                ).get("EndpointGroup")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to update AWS Global Accelerator endpoint "
                        f"group {endpoint_group_arn}"
                    ),
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

        try:
            client.update_listener(
                **request,
                aws_retry=True,
            )
        except Exception as e:
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

        try:
            listener = client.create_listener(
                **request,
                aws_retry=True,
            ).get("Listener")
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to create AWS Global Accelerator listener for "
                    f"{accelerator_arn}"
                ),
            )

        result["listener_arn"] = (listener or {}).get("ListenerArn")
        result_listeners.append((result, desired))

    if not module.check_mode:
        for current in deletes:
            delete_listener(client, module, current["listener_arn"])

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

        for listener in get_listeners(client, module, accelerator_arn):
            delete_listener(client, module, listener["listener_arn"])

        if accelerator.get("Enabled"):
            try:
                client.update_accelerator(
                    AcceleratorArn=accelerator_arn,
                    Enabled=False,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to disable AWS Global Accelerator " f"{accelerator_arn}"
                    ),
                )

        if module.params["wait"]:
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deployed",
            )

        try:
            client.delete_accelerator(
                AcceleratorArn=accelerator_arn,
                aws_retry=True,
            )
        except Exception as e:
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

    if ip_addresses:
        desired["ip_addresses"] = sorted(ip_addresses)

    accelerator = get_accelerator(client, module)
    created = accelerator is None

    current_tags = {}
    if accelerator is not None and tags is not None:
        accelerator_arn = accelerator["AcceleratorArn"]

        try:
            current_tags = boto3_tag_list_to_ansible_dict(
                client.list_tags_for_resource(
                    ResourceArn=accelerator_arn,
                    aws_retry=True,
                ).get("Tags", [])
            )
        except Exception as e:
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

        if ip_addresses:
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
                    "ip_addresses": ip_addresses or None,
                    "ip_address_type": desired["ip_address_type"],
                    "name": desired["name"],
                    "tags": (
                        ansible_dict_to_boto3_tag_list(tags)
                        if tags is not None
                        else None
                    ),
                },
                capitalize_first=True,
            )
        )

        try:
            accelerator = client.create_accelerator(
                **request,
                aws_retry=True,
            ).get("Accelerator")
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Global Accelerator {desired['name']}",
            )
    elif created and module.check_mode:
        accelerator = {
            "Enabled": desired["enabled"],
            "IpAddressType": desired["ip_address_type"],
            "Name": desired["name"],
            "Status": "IN_PROGRESS",
        }
        if ip_addresses:
            accelerator["IpSets"] = [{"IpAddresses": ip_addresses}]
    elif resource_changed and not module.check_mode:
        request = scrub_none_parameters(
            snake_dict_to_camel_dict(
                {
                    "accelerator_arn": accelerator["AcceleratorArn"],
                    "enabled": desired["enabled"],
                    "ip_addresses": ip_addresses or None,
                    "ip_address_type": desired["ip_address_type"],
                    "name": desired["name"],
                },
                capitalize_first=True,
            )
        )

        try:
            accelerator = client.update_accelerator(
                **request,
                aws_retry=True,
            ).get("Accelerator")
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to update AWS Global Accelerator "
                    f"{request['AcceleratorArn']}"
                ),
            )
    elif resource_changed and module.check_mode:
        accelerator = dict(accelerator)
        accelerator["Enabled"] = desired["enabled"]
        accelerator["IpAddressType"] = desired["ip_address_type"]
        accelerator["Name"] = desired["name"]
        if ip_addresses:
            accelerator["IpSets"] = [{"IpAddresses": ip_addresses}]

    listeners = None
    listeners_changed = False
    if module.params["listeners"] is not None:
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
            if tag_keys_to_unset:
                try:
                    client.untag_resource(
                        ResourceArn=accelerator_arn,
                        TagKeys=tag_keys_to_unset,
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to remove tags from AWS Global Accelerator "
                            f"{accelerator_arn}"
                        ),
                    )

            if tags_to_set:
                try:
                    client.tag_resource(
                        ResourceArn=accelerator_arn,
                        Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=f"Unable to tag AWS Global Accelerator {accelerator_arn}",
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

    require_positive_wait_bounds(module)

    for listener in module.params["listeners"] or []:
        if not listener["port_ranges"]:
            module.fail_json(
                msg="listeners entries require at least one port_ranges entry"
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

        for endpoint_group in listener["endpoint_groups"] or []:
            region = endpoint_group["endpoint_group_region"]

            if endpoint_group["health_check_port"] is not None and not (
                1 <= endpoint_group["health_check_port"] <= 65535
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} health_check_port must be "
                        "between 1 and 65535"
                    )
                )

            if endpoint_group["threshold_count"] is not None and not (
                1 <= endpoint_group["threshold_count"] <= 10
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} threshold_count must be "
                        "between 1 and 10"
                    )
                )

            if endpoint_group["traffic_dial_percentage"] is not None and not (
                0 <= endpoint_group["traffic_dial_percentage"] <= 100
            ):
                module.fail_json(
                    msg=(
                        f"Endpoint group {region} traffic_dial_percentage "
                        "must be between 0 and 100"
                    )
                )

            for configuration in endpoint_group["endpoint_configurations"] or []:
                if not 0 <= configuration["weight"] <= 255:
                    module.fail_json(
                        msg=(
                            f"Endpoint group {region} endpoint_configurations "
                            "weight must be between 0 and 255"
                        )
                    )

            for port_override in endpoint_group["port_overrides"] or []:
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

    client = module.client(
        "globalaccelerator",
        region="us-west-2",
        retry_decorator=AWSRetry.jittered_backoff(),
    )

    state = module.params["state"]
    method_names = {"describe_accelerator"}
    if module.params["arn"] is None:
        method_names.add("list_accelerators")
    if state == "present":
        method_names.update(
            {
                "create_accelerator",
                "update_accelerator",
            }
        )
        if module.params["tags"] is not None:
            method_names.add("list_tags_for_resource")
            method_names.add("tag_resource")
            if module.params["purge_tags"]:
                method_names.add("untag_resource")
        if module.params["listeners"] is not None:
            method_names.update(
                {
                    "create_listener",
                    "list_listeners",
                    "update_listener",
                }
            )
            if module.params["purge_listeners"]:
                method_names.update(
                    {
                        "delete_endpoint_group",
                        "delete_listener",
                        "list_endpoint_groups",
                    }
                )

            for listener in module.params["listeners"]:
                if listener["endpoint_groups"] is None:
                    continue

                method_names.update(
                    {
                        "create_endpoint_group",
                        "list_endpoint_groups",
                        "update_endpoint_group",
                    }
                )
                if module.params["purge_endpoint_groups"]:
                    method_names.add("delete_endpoint_group")

    if state == "absent":
        method_names.update(
            {
                "delete_accelerator",
                "delete_endpoint_group",
                "delete_listener",
                "list_endpoint_groups",
                "list_listeners",
                "update_accelerator",
            }
        )

    required_method_parameters = {
        "create_accelerator": {
            "Enabled",
            "IdempotencyToken",
            "IpAddresses",
            "IpAddressType",
            "Name",
            "Tags",
        },
        "create_endpoint_group": {
            "EndpointConfigurations",
            "EndpointGroupRegion",
            "HealthCheckIntervalSeconds",
            "HealthCheckPath",
            "HealthCheckPort",
            "HealthCheckProtocol",
            "IdempotencyToken",
            "ListenerArn",
            "PortOverrides",
            "ThresholdCount",
            "TrafficDialPercentage",
        },
        "create_listener": {
            "AcceleratorArn",
            "ClientAffinity",
            "IdempotencyToken",
            "PortRanges",
            "Protocol",
        },
        "delete_accelerator": {"AcceleratorArn"},
        "delete_endpoint_group": {"EndpointGroupArn"},
        "delete_listener": {"ListenerArn"},
        "describe_accelerator": {"AcceleratorArn"},
        "list_accelerators": {"MaxResults", "NextToken"},
        "list_endpoint_groups": {"ListenerArn", "MaxResults", "NextToken"},
        "list_listeners": {"AcceleratorArn", "MaxResults", "NextToken"},
        "list_tags_for_resource": {"ResourceArn"},
        "tag_resource": {"ResourceArn", "Tags"},
        "untag_resource": {"ResourceArn", "TagKeys"},
        "update_accelerator": {
            "AcceleratorArn",
            "Enabled",
            "IpAddresses",
            "IpAddressType",
            "Name",
        },
        "update_endpoint_group": {
            "EndpointConfigurations",
            "EndpointGroupArn",
            "HealthCheckIntervalSeconds",
            "HealthCheckPath",
            "HealthCheckPort",
            "HealthCheckProtocol",
            "PortOverrides",
            "ThresholdCount",
            "TrafficDialPercentage",
        },
        "update_listener": {
            "ClientAffinity",
            "ListenerArn",
            "PortRanges",
            "Protocol",
        },
    }
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {name: required_method_parameters.get(name, ()) for name in method_names},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
