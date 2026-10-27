#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: global_accelerator
version_added: "1.9.0"
short_description: Manage AWS Global Accelerator accelerators
description:
  - Manages AWS Global Accelerator accelerators, their listeners, and their
    endpoint groups as one resource tree.
  - Listener updates release conflicting ports before dependent updates.
  - Circular listener port dependencies fail before listener changes and require an intermediate configuration.
  - Listener entries in O(listeners) that exactly match an existing listener's
    protocol and port ranges keep that listener. When O(purge_listeners=true),
    remaining entries update existing listeners with the same protocol in
    place, new listeners are created for the rest, and existing listeners not
    present in O(listeners) are deleted, including their endpoint groups.
  - When O(purge_listeners=false), remaining entries always create new
    listeners and existing listeners not present in O(listeners) are left
    unchanged; the module fails before any listener change when a new
    listener's ports overlap one of those existing listeners.
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
      - When omitted while creating an accelerator, AWS enables it.
      - When omitted while updating an accelerator, the existing value is left unchanged.
    type: bool
  idempotency_token:
    description:
      - Unique idempotency token for accelerator creation.
      - When omitted, a unique token is generated for each creation attempt.
      - This option is only used when creating an accelerator.
      - This must contain at most 255 characters.
    type: str
  ip_addresses:
    description:
      - Static IP addresses to assign to the accelerator.
      - These must be IP addresses from an AWS Global Accelerator BYOIP address pool.
      - This must contain at most 2 entries.
      - When omitted, AWS assigns IP addresses.
      - Additional AWS-assigned addresses do not cause updates when all requested addresses are present.
      - This can only be set when creating an accelerator.
      - When an existing accelerator does not have all requested addresses, the module fails without modifying it.
      - An empty list is treated as omitted. Assigned static addresses cannot be cleared from an existing accelerator.
    elements: str
    type: list
  ip_address_type:
    description:
      - IP address type for the accelerator.
      - When omitted while creating an accelerator, AWS uses C(IPV4).
      - When omitted while updating an accelerator, the existing value is left unchanged.
    choices:
      - DUAL_STACK
      - IPV4
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
          - When omitted while creating a listener, AWS uses C(NONE).
          - When omitted while updating a listener, the existing value is left unchanged.
        choices:
          - NONE
          - SOURCE_IP
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
                  - Used for create and update requests. AWS does not return
                    this ARN in endpoint descriptions, so it is not compared
                    when determining whether an existing endpoint needs updating.
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
                  - This must not be empty.
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
              - This must not be empty and must contain at most 255 characters.
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
              - AWS does not store a path for C(TCP) health checks, so this is
                not compared when the health check protocol is C(TCP).
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
  state:
    description:
      - Whether the accelerator should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  wait:
    description:
      - Whether to wait for the accelerator to finish deploying after changes
        are applied, and for the accelerator deletion to complete when
        O(state=absent).
      - Accelerator, listener, and endpoint group changes are applied first
        and share a single deployment wait.
      - Even when O(wait=false), the module waits for an accelerator that is still deploying before
        changing it or managing its listeners, for a new accelerator to deploy before creating its
        listeners, between dependent listener changes, after deleting a listener's endpoint groups
        before deleting the listener, and before endpoint group changes. When O(state=absent), it
        also waits for listener and endpoint group deletions and for the accelerator to be disabled,
        because AWS deletes an accelerator only after these deploy. These waits use O(wait_delay) and
        are bounded by O(wait_timeout).
    default: true
    type: bool
  wait_delay:
    description:
      - The delay in seconds between accelerator status polling attempts.
      - This also applies to the waits that happen even when O(wait=false).
      - This must be 1 or greater.
    default: 10
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait.
      - Also bounds the waits that happen even when O(wait=false).
      - Sequential waits in one run share this budget.
      - This must be 1 or greater.
    default: 600
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts accelerator, listener, endpoint group, and tag changes without modifying AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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
  returned: when O(state=present)
  type: dict
  contains:
    accelerator_arn:
      description: The accelerator ARN.
      returned: when the accelerator exists
      type: str
    created_time:
      description: The time the accelerator was created.
      returned: when returned by AWS
      type: str
    dns_name:
      description: The IPv4 DNS name of the accelerator.
      returned: when returned by AWS
      type: str
    dual_stack_dns_name:
      description: The dual-stack DNS name of the accelerator.
      returned: when the accelerator is dual-stack
      type: str
    enabled:
      description: Whether the accelerator is enabled.
      returned: always
      type: bool
    events:
      description: The accelerator events, such as those reporting failed IP address transfers.
      returned: when returned by AWS
      type: list
      elements: dict
      contains:
        message:
          description: The event message.
          returned: when returned by AWS
          type: str
        timestamp:
          description: The time the event occurred.
          returned: when returned by AWS
          type: str
    ip_address_type:
      description: The accelerator IP address type.
      returned: always
      type: str
      sample: IPV4
    ip_sets:
      description: The static IP addresses assigned to the accelerator.
      returned: when returned by AWS
      type: list
      elements: dict
      contains:
        ip_address_family:
          description: The IP address family.
          returned: when returned by AWS
          type: str
        ip_addresses:
          description: The IP addresses.
          returned: always
          type: list
          elements: str
        ip_family:
          description:
            - The IP address family.
            - AWS deprecates this field in favor of C(ip_address_family).
          returned: when returned by AWS
          type: str
    last_modified_time:
      description: The time the accelerator was last modified.
      returned: when returned by AWS
      type: str
    name:
      description: The accelerator name.
      returned: always
      type: str
    status:
      description: The accelerator deployment status.
      returned: when returned by AWS
      type: str
      sample: DEPLOYED
    tags:
      description: The accelerator tags with key case preserved.
      returned: when O(tags) is provided
      type: dict
    listeners:
      description: The accelerator listeners.
      returned: when O(listeners) is provided
      type: list
      elements: dict
      contains:
        client_affinity:
          description: The listener client affinity.
          returned: always
          type: str
          sample: NONE
        endpoint_groups:
          description: The listener endpoint groups.
          returned: when O(listeners[].endpoint_groups) is provided
          type: list
          elements: dict
          contains:
            endpoint_descriptions:
              description: The endpoints in the endpoint group.
              returned: when returned by AWS
              type: list
              elements: dict
              contains:
                client_ip_preservation_enabled:
                  description: Whether client IP address preservation is enabled.
                  returned: when returned by AWS
                  type: bool
                endpoint_id:
                  description: The endpoint ID.
                  returned: always
                  type: str
                health_reason:
                  description: The reason for the endpoint health state.
                  returned: when returned by AWS
                  type: str
                health_state:
                  description: The endpoint health state.
                  returned: when returned by AWS
                  type: str
                weight:
                  description: The endpoint weight.
                  returned: when returned by AWS
                  type: int
            endpoint_group_arn:
              description: The endpoint group ARN.
              returned: when the endpoint group exists
              type: str
            endpoint_group_region:
              description: The endpoint group region.
              returned: always
              type: str
            health_check_interval_seconds:
              description: The time in seconds between health checks.
              returned: when returned by AWS
              type: int
            health_check_path:
              description: The health check path.
              returned: when returned by AWS
              type: str
            health_check_port:
              description: The health check port.
              returned: when returned by AWS
              type: int
            health_check_protocol:
              description: The health check protocol.
              returned: when returned by AWS
              type: str
            port_overrides:
              description: The listener to endpoint port overrides.
              returned: when returned by AWS
              type: list
              elements: dict
              contains:
                endpoint_port:
                  description: The endpoint port.
                  returned: always
                  type: int
                listener_port:
                  description: The listener port.
                  returned: always
                  type: int
            threshold_count:
              description: The number of health checks required to change endpoint health.
              returned: when returned by AWS
              type: int
            traffic_dial_percentage:
              description: The percentage of traffic sent to the endpoint group.
              returned: when returned by AWS
              type: float
        listener_arn:
          description: The listener ARN.
          returned: when the listener exists
          type: str
        port_ranges:
          description: The listener port ranges.
          returned: always
          type: list
          elements: dict
          contains:
            from_port:
              description: The first port in the range.
              returned: always
              type: int
            to_port:
              description: The last port in the range.
              returned: always
              type: int
        protocol:
          description: The listener protocol.
          returned: always
          type: str
          sample: TCP
accelerator_arn:
  description:
    - ARN of the accelerator.
  returned: when O(state=present) and the accelerator exists
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import ipaddress
import re
import uuid

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

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

from ansible_collections.linuxhq.aws.plugins.module_utils.global_accelerator import list_accelerator_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    reconcile_arn_tags,
    require_resulting_tag_limit,
    require_valid_tags,
    updated_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    custom_waiter,
    require_positive_wait_bounds,
    run_waiter,
    wait_deadline,
)

# Scalar endpoint group settings and their request parameters.
ENDPOINT_GROUP_SETTINGS = {
    "health_check_interval_seconds": "HealthCheckIntervalSeconds",
    "health_check_path": "HealthCheckPath",
    "health_check_port": "HealthCheckPort",
    "health_check_protocol": "HealthCheckProtocol",
    "threshold_count": "ThresholdCount",
    "traffic_dial_percentage": "TrafficDialPercentage",
}

# AWS stores these values for endpoint group settings that a create omits.
ENDPOINT_GROUP_CREATE_DEFAULTS = {
    "health_check_interval_seconds": 30,
    "health_check_protocol": "TCP",
    "threshold_count": 3,
    "traffic_dial_percentage": 100.0,
}

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
    # An accelerator that another actor is deleting is gone instead of deployed when the wait ends.
    "accelerator_deployed_or_deleted": {
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


def validate_accelerator(module, accelerator, expected_arn=None, changed=False):
    ip_sets = accelerator.get("IpSets") if isinstance(accelerator, dict) else None
    if (
        not isinstance(accelerator, dict)
        or not isinstance(accelerator.get("AcceleratorArn"), str)
        or not accelerator["AcceleratorArn"]
        or (expected_arn is not None and accelerator["AcceleratorArn"] != expected_arn)
        or not isinstance(accelerator.get("Name"), str)
        or not isinstance(accelerator.get("Enabled"), bool)
        or not isinstance(accelerator.get("IpAddressType"), str)
        or ("Status" in accelerator and not isinstance(accelerator["Status"], str))
        or (ip_sets is not None and not isinstance(ip_sets, list))
        or (
            isinstance(ip_sets, list)
            and any(
                not isinstance(ip_set, dict)
                or not isinstance(ip_set.get("IpAddresses"), list)
                or any(not isinstance(address, str) for address in ip_set["IpAddresses"])
                for ip_set in ip_sets
            )
        )
    ):
        module.fail_json(changed=changed, msg="Global Accelerator returned an invalid accelerator")

    return accelerator


def validate_listener(module, listener, changed=False):
    port_ranges = listener.get("PortRanges") if isinstance(listener, dict) else None
    if (
        not isinstance(listener, dict)
        or not isinstance(listener.get("ListenerArn"), str)
        or not listener["ListenerArn"]
        or not isinstance(listener.get("ClientAffinity"), str)
        or not isinstance(listener.get("Protocol"), str)
        or not isinstance(port_ranges, list)
        or any(
            not isinstance(port_range, dict)
            or not isinstance(port_range.get("FromPort"), int)
            or not isinstance(port_range.get("ToPort"), int)
            for port_range in port_ranges
        )
    ):
        module.fail_json(changed=changed, msg="Global Accelerator returned an invalid listener")

    return listener


def validate_endpoint_group(module, endpoint_group, expected_arn=None, expected_region=None, changed=False):
    endpoint_descriptions = endpoint_group.get("EndpointDescriptions") if isinstance(endpoint_group, dict) else None
    port_overrides = endpoint_group.get("PortOverrides") if isinstance(endpoint_group, dict) else None
    if (
        not isinstance(endpoint_group, dict)
        or not isinstance(endpoint_group.get("EndpointGroupArn"), str)
        or not endpoint_group["EndpointGroupArn"]
        or (expected_arn is not None and endpoint_group["EndpointGroupArn"] != expected_arn)
        or not isinstance(endpoint_group.get("EndpointGroupRegion"), str)
        or (expected_region is not None and endpoint_group["EndpointGroupRegion"] != expected_region)
        or (endpoint_descriptions is not None and not isinstance(endpoint_descriptions, list))
        or (
            isinstance(endpoint_descriptions, list)
            and any(
                not isinstance(endpoint, dict) or not isinstance(endpoint.get("EndpointId"), str)
                for endpoint in endpoint_descriptions
            )
        )
        or (port_overrides is not None and not isinstance(port_overrides, list))
        or (
            isinstance(port_overrides, list)
            and any(
                not isinstance(port_override, dict)
                or not isinstance(port_override.get("EndpointPort"), int)
                or not isinstance(port_override.get("ListenerPort"), int)
                for port_override in port_overrides
            )
        )
    ):
        module.fail_json(changed=changed, msg="Global Accelerator returned an invalid endpoint group")

    return endpoint_group


def get_accelerator_by_arn(client, module, accelerator_arn, changed=False):
    """Describe an accelerator; changed reports whether it was already modified, for failure results."""
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"describe_accelerator": ("AcceleratorArn",)},
        changed=changed,
    )
    try:
        response = client.describe_accelerator(
            AcceleratorArn=accelerator_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("AcceleratorNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=f"Unable to describe AWS Global Accelerator {accelerator_arn}")

    return validate_accelerator(
        module,
        response.get("Accelerator") if isinstance(response, dict) else None,
        expected_arn=accelerator_arn,
        changed=changed,
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

    if not isinstance(accelerators, list):
        module.fail_json(msg="Global Accelerator returned an invalid accelerator list")

    accelerators = [validate_accelerator(module, accelerator) for accelerator in accelerators]

    matches = [accelerator for accelerator in accelerators if accelerator.get("Name") == name]

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


def wait_for_accelerator(client, module, accelerator_arn, waiter_name, changed=False, deadline=None):
    """Wait for an accelerator; changed reports whether it was already modified, for failure results.

    deadline limits the wait to what is left of the run's shared wait_timeout budget.
    """
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"describe_accelerator": ("AcceleratorArn",)},
        changed=changed,
    )
    run_waiter(
        module,
        custom_waiter(client, GLOBAL_ACCELERATOR_WAITER_MODEL_DATA, waiter_name),
        f"Timed out waiting for AWS Global Accelerator {accelerator_arn}",
        changed=changed,
        deadline=deadline,
        AcceleratorArn=accelerator_arn,
    )


def normalized_port_ranges(port_ranges):
    return sorted(
        ({"from_port": item["from_port"], "to_port": item["to_port"]} for item in port_ranges),
        key=lambda item: (item["from_port"], item["to_port"]),
    )


def listener_identity(listener):
    return (
        listener["protocol"],
        tuple((port_range["from_port"], port_range["to_port"]) for port_range in listener["port_ranges"]),
    )


def get_listeners(client, module, accelerator_arn, changed=False):
    """List listeners; changed reports whether the accelerator was already modified, for failure results."""
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"list_listeners": ("AcceleratorArn", "MaxResults", "NextToken")},
        changed=changed,
    )
    listeners = query_list(
        module,
        client,
        "list_listeners",
        "Listeners",
        f"Unable to list AWS Global Accelerator listeners for {accelerator_arn}",
        changed=changed,
        AcceleratorArn=accelerator_arn,
    )
    if not isinstance(listeners, list):
        module.fail_json(changed=changed, msg="Global Accelerator returned an invalid listener list")

    listeners = [validate_listener(module, listener, changed=changed) for listener in listeners]

    normalized = []
    for listener in listeners:
        port_ranges = [
            {
                "from_port": port_range["FromPort"],
                "to_port": port_range["ToPort"],
            }
            for port_range in listener["PortRanges"]
        ]

        normalized.append(
            {
                "client_affinity": listener["ClientAffinity"],
                "listener_arn": listener["ListenerArn"],
                "port_ranges": normalized_port_ranges(port_ranges),
                "protocol": listener["Protocol"],
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
        match = next(
            (current for current in remaining if listener_identity(current) == listener_identity(desired)), None
        )

        if match is None:
            pending.append(desired)
            continue

        remaining.remove(match)
        if desired["client_affinity"] is not None and match["client_affinity"] != desired["client_affinity"]:
            updates.append((match, desired))
        else:
            matched.append((match, desired))

    for desired in pending:
        # Only listeners that would otherwise be purged are reused for other ports.
        match = None
        if module.params["purge_listeners"]:
            match = next((current for current in remaining if current["protocol"] == desired["protocol"]), None)

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
    return scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "client_affinity": desired["client_affinity"],
                "port_ranges": desired["port_ranges"],
                "protocol": desired["protocol"],
            },
            capitalize_first=True,
        )
    )


def port_ranges_overlap(left, right):
    return left["from_port"] <= right["to_port"] and right["from_port"] <= left["to_port"]


def listeners_overlap(first, second):
    return first["protocol"] == second["protocol"] and any(
        port_ranges_overlap(left, right) for left in first["port_ranges"] for right in second["port_ranges"]
    )


def ordered_listener_updates(module, updates, changed=False):
    """Order listener updates; changed reports earlier modifications, for failure results."""
    pending = list(updates)
    ordered = []
    while pending:
        for current, desired in pending:
            if not any(other is not current and listeners_overlap(other, desired) for other, unused_desired in pending):
                ordered.append((current, desired))
                pending.remove((current, desired))
                break
        else:
            module.fail_json(
                changed=changed,
                msg="Unable to update AWS Global Accelerator listeners: circular port dependencies; "
                "apply an intermediate configuration that releases the conflicting ports first",
            )

    return ordered


def normalized_port_overrides(port_overrides):
    return sorted(
        (
            {
                "endpoint_port": item["endpoint_port"],
                "listener_port": item["listener_port"],
            }
            for item in port_overrides or []
        ),
        key=lambda item: (item["listener_port"], item["endpoint_port"]),
    )


def get_endpoint_groups(client, module, listener_arn, changed=False):
    """List endpoint groups; changed reports whether the accelerator was already modified, for failure results."""
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"list_endpoint_groups": ("ListenerArn", "MaxResults", "NextToken")},
        changed=changed,
    )
    endpoint_groups = query_list(
        module,
        client,
        "list_endpoint_groups",
        "EndpointGroups",
        f"Unable to list AWS Global Accelerator endpoint groups for {listener_arn}",
        changed=changed,
        ListenerArn=listener_arn,
    )
    if not isinstance(endpoint_groups, list):
        module.fail_json(changed=changed, msg="Global Accelerator returned an invalid endpoint group list")

    endpoint_groups = [
        validate_endpoint_group(module, endpoint_group, changed=changed) for endpoint_group in endpoint_groups
    ]

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
    # AWS stores no health check path for TCP health checks, so a requested path never matches one.
    tcp_health_check = (desired["health_check_protocol"] or current.get("health_check_protocol")) == "TCP"
    for field in ENDPOINT_GROUP_SETTINGS:
        if field == "health_check_path" and tcp_health_check:
            continue

        if desired[field] is not None and desired[field] != current.get(field):
            return True

    if desired["port_overrides"] is not None:
        current_overrides = normalized_port_overrides(current.get("port_overrides"))

        if normalized_port_overrides(desired["port_overrides"]) != current_overrides:
            return True

    if desired["endpoint_configurations"] is not None:
        current_endpoints = {
            endpoint.get("endpoint_id"): endpoint for endpoint in current.get("endpoint_descriptions", [])
        }
        desired_ids = {configuration["endpoint_id"] for configuration in desired["endpoint_configurations"]}

        if desired_ids != set(current_endpoints):
            return True

        for configuration in desired["endpoint_configurations"]:
            endpoint = current_endpoints[configuration["endpoint_id"]]

            if configuration["weight"] != endpoint.get("weight"):
                return True

            if configuration["client_ip_preservation_enabled"] is not None and configuration[
                "client_ip_preservation_enabled"
            ] != endpoint.get("client_ip_preservation_enabled"):
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
                entry["ClientIPPreservationEnabled"] = configuration["client_ip_preservation_enabled"]

            if configuration["attachment_arn"] is not None:
                entry["AttachmentArn"] = configuration["attachment_arn"]

            configurations.append(entry)

        request["EndpointConfigurations"] = configurations

    for field, request_field in ENDPOINT_GROUP_SETTINGS.items():
        if desired[field] is not None:
            request[request_field] = desired[field]

    if desired["port_overrides"] is not None:
        request["PortOverrides"] = [
            {
                "EndpointPort": item["endpoint_port"],
                "ListenerPort": item["listener_port"],
            }
            for item in desired["port_overrides"]
        ]

    return request


def require_endpoint_configuration_parameters(module, client, method_name, operation_name, request):
    configurations = request.get("EndpointConfigurations")
    if not configurations:
        return

    available_parameters = (
        client.meta.service_model.operation_model(operation_name)
        .input_shape.members["EndpointConfigurations"]
        .member.members
    )
    requested_parameters = {parameter for configuration in configurations for parameter in configuration}
    for parameter_name in sorted(requested_parameters):
        if parameter_name not in available_parameters:
            module.fail_json(
                msg=(
                    "Installed botocore does not support Global Accelerator "
                    f"{method_name} EndpointConfigurations parameter "
                    f"{parameter_name}"
                )
            )


def require_listener_writes(module, client):
    """Check every listener write the requested listeners can need, before the first change."""
    listeners = module.params["listeners"]

    # Whether a listener is updated or created is known only after listing it, so both writes are checked.
    methods = {}
    if listeners:
        parameters = {"AcceleratorArn", "IdempotencyToken", "PortRanges", "Protocol"}
        if any(listener["client_affinity"] is not None for listener in listeners):
            parameters.add("ClientAffinity")

        methods["create_listener"] = tuple(sorted(parameters))
        # Updates always send the current ClientAffinity when it is omitted.
        methods["update_listener"] = ("ClientAffinity", "ListenerArn", "PortRanges", "Protocol")

    if module.params["purge_listeners"]:
        # Deleting a listener deletes its endpoint groups first.
        methods["delete_endpoint_group"] = ("EndpointGroupArn",)
        methods["delete_listener"] = ("ListenerArn",)

    if methods:
        require_client_methods(module, client, "Global Accelerator", methods)


def require_endpoint_group_writes(module, client):
    """Check every endpoint group write the requested listeners can need, before the first change."""
    if all(listener["endpoint_groups"] is None for listener in module.params["listeners"]):
        return

    requests = [
        endpoint_group_request(desired)
        for listener in module.params["listeners"]
        for desired in listener["endpoint_groups"] or []
    ]

    # Whether a group is created or updated is known only after listing it, so both writes are checked.
    parameters = {parameter for request in requests for parameter in request}
    methods = {}
    if requests:
        methods["create_endpoint_group"] = tuple(
            sorted(parameters | {"EndpointGroupRegion", "IdempotencyToken", "ListenerArn"})
        )
        methods["update_endpoint_group"] = tuple(sorted(parameters | {"EndpointGroupArn"}))

    if module.params["purge_endpoint_groups"]:
        methods["delete_endpoint_group"] = ("EndpointGroupArn",)

    if methods:
        require_client_methods(module, client, "Global Accelerator", methods)

    for request in requests:
        for method_name, operation_name in (
            ("create_endpoint_group", "CreateEndpointGroup"),
            ("update_endpoint_group", "UpdateEndpointGroup"),
        ):
            require_endpoint_configuration_parameters(module, client, method_name, operation_name, request)


def predicted_endpoint_group(current, desired, default_health_check_port=None):
    if current is None:
        # AWS returns an empty endpoint list for a group created without endpoints.
        predicted = dict(ENDPOINT_GROUP_CREATE_DEFAULTS, endpoint_descriptions=[])
        if default_health_check_port is not None:
            predicted["health_check_port"] = default_health_check_port
    else:
        predicted = dict(current)

    predicted["endpoint_group_region"] = desired["endpoint_group_region"]

    for field in ENDPOINT_GROUP_SETTINGS:
        if desired[field] is not None:
            predicted[field] = desired[field]

    # AWS stores a health check path only for HTTP and HTTPS health checks, and defaults it to /.
    if predicted.get("health_check_protocol") == "TCP":
        predicted.pop("health_check_path", None)
    elif predicted.get("health_check_protocol") in ("HTTP", "HTTPS"):
        predicted.setdefault("health_check_path", "/")

    if desired["port_overrides"] is not None:
        predicted["port_overrides"] = normalized_port_overrides(desired["port_overrides"])

    if desired["endpoint_configurations"] is not None:
        endpoint_descriptions = []
        for configuration in desired["endpoint_configurations"]:
            endpoint = {
                "endpoint_id": configuration["endpoint_id"],
                "weight": configuration["weight"],
            }
            if configuration["client_ip_preservation_enabled"] is not None:
                endpoint["client_ip_preservation_enabled"] = configuration["client_ip_preservation_enabled"]

            endpoint_descriptions.append(endpoint)

        predicted["endpoint_descriptions"] = endpoint_descriptions

    return predicted


def delete_endpoint_group(client, module, endpoint_group_arn, changed=False):
    """Delete an endpoint group; changed reports earlier modifications, for failure results."""
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"delete_endpoint_group": ("EndpointGroupArn",)},
        changed=changed,
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
            changed=changed,
            msg=f"Unable to delete AWS Global Accelerator endpoint group {endpoint_group_arn}",
        )


def delete_listener(client, module, accelerator_arn, listener_arn, changed=False, deadline=None):
    """Delete a listener and its endpoint groups; changed reports earlier modifications, for failure results."""
    require_client_methods(
        module,
        client,
        "Global Accelerator",
        {"delete_listener": ("ListenerArn",)},
        changed=changed,
    )
    endpoint_groups = get_endpoint_groups(client, module, listener_arn, changed=changed)
    for endpoint_group in endpoint_groups:
        delete_endpoint_group(client, module, endpoint_group["endpoint_group_arn"], changed=changed)
        changed = True

    if endpoint_groups:
        wait_for_accelerator(client, module, accelerator_arn, "accelerator_deployed", changed=True, deadline=deadline)

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
            changed=changed,
            msg=f"Unable to delete AWS Global Accelerator listener {listener_arn}",
        )


def ensure_endpoint_groups(
    client, module, listener_arn, endpoint_groups, mutated=False, default_health_check_port=None
):
    """Reconcile endpoint groups; mutated reports earlier modifications, for failure results.

    default_health_check_port is the port AWS checks health on when a created group omits health_check_port, if it is
    known, for check-mode predictions.
    """
    current_by_region = {}
    if listener_arn is not None:
        for endpoint_group in get_endpoint_groups(client, module, listener_arn, changed=mutated):
            current_by_region[endpoint_group["endpoint_group_region"]] = endpoint_group

    changed = False
    results = []

    for desired in endpoint_groups:
        region = desired["endpoint_group_region"]

        current = current_by_region.pop(region, None)

        if current is None:
            changed = True
            if module.check_mode:
                results.append(predicted_endpoint_group(None, desired, default_health_check_port))
                continue

            request = endpoint_group_request(desired)
            request["EndpointGroupRegion"] = region
            # A fixed token would replay an earlier create, even one modified since; AWSRetry reuses this one.
            request["IdempotencyToken"] = str(uuid.uuid4())
            request["ListenerArn"] = listener_arn

            try:
                response = client.create_endpoint_group(
                    **request,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    changed=mutated,
                    msg=f"Unable to create AWS Global Accelerator endpoint group {region} for {listener_arn}",
                )

            mutated = True
            endpoint_group = validate_endpoint_group(
                module,
                response.get("EndpointGroup") if isinstance(response, dict) else None,
                expected_region=region,
                changed=True,
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
                response = client.update_endpoint_group(
                    **request,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    changed=mutated,
                    msg=f"Unable to update AWS Global Accelerator endpoint group {endpoint_group_arn}",
                )

            mutated = True
            endpoint_group = validate_endpoint_group(
                module,
                response.get("EndpointGroup") if isinstance(response, dict) else None,
                expected_arn=endpoint_group_arn,
                changed=True,
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
                delete_endpoint_group(client, module, endpoint_group["endpoint_group_arn"], changed=mutated)
                mutated = True
    else:
        results.extend(remaining)

    results = sorted(results, key=lambda item: item["endpoint_group_region"])
    return changed, results


def ensure_listeners(client, module, accelerator_arn, mutated=False, deadline=None):
    """Reconcile listeners; mutated reports earlier modifications, for failure results."""
    current_listeners = []
    if accelerator_arn is not None:
        current_listeners = get_listeners(client, module, accelerator_arn, changed=mutated)

    matched, updates, creates, deletes = reconcile_listeners(module, current_listeners)
    changed = bool(updates or creates or deletes)
    result_listeners = []

    updates = ordered_listener_updates(module, updates, changed=mutated)
    desired_changes = [desired for current, desired in updates] + creates
    for current, unused_desired in matched:
        if any(listeners_overlap(current, desired) for desired in desired_changes):
            module.fail_json(
                changed=mutated,
                msg="Unable to update AWS Global Accelerator listeners: desired ports overlap retained listener "
                f"{current['listener_arn']}",
            )

    # Build every listener write before releasing any ports.
    update_requests = {}
    create_requests = []
    if not module.check_mode:
        for current, desired in updates:
            # UpdateListener documents NONE as the ClientAffinity default, so the current value is kept explicitly.
            request = listener_request(
                dict(desired, client_affinity=desired["client_affinity"] or current["client_affinity"])
            )
            request["ListenerArn"] = current["listener_arn"]
            update_requests[current["listener_arn"]] = request

        for desired in creates:
            request = listener_request(desired)
            request["AcceleratorArn"] = accelerator_arn
            # A fixed token would replay an earlier create, even one modified since; AWSRetry reuses this one.
            request["IdempotencyToken"] = str(uuid.uuid4())
            create_requests.append(request)

    # Release only obsolete listeners that block the validated writes.
    conflicting_deletes = [
        current for current in deletes if any(listeners_overlap(current, desired) for desired in desired_changes)
    ]
    if conflicting_deletes and not module.check_mode:
        for current in conflicting_deletes:
            delete_listener(
                client, module, accelerator_arn, current["listener_arn"], changed=mutated, deadline=deadline
            )
            mutated = True
            deletes.remove(current)

        wait_for_accelerator(client, module, accelerator_arn, "accelerator_deployed", changed=True, deadline=deadline)

    # Each entry also records whether this run sends the listener's port ranges, which it sends sorted.
    for current, desired in matched:
        result_listeners.append((dict(current), desired, False))

    for current, desired in updates:
        listener_arn = current["listener_arn"]
        result = {
            "client_affinity": desired["client_affinity"] or current["client_affinity"],
            "listener_arn": listener_arn,
            "port_ranges": desired["port_ranges"],
            "protocol": desired["protocol"],
        }
        result_listeners.append((result, desired, True))

        if module.check_mode:
            continue

        request = update_requests[listener_arn]
        try:
            response = client.update_listener(
                **request,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                changed=mutated,
                msg=f"Unable to update AWS Global Accelerator listener {listener_arn}",
            )

        mutated = True
        listener = validate_listener(
            module,
            response.get("Listener") if isinstance(response, dict) else None,
            changed=True,
        )
        result["client_affinity"] = listener["ClientAffinity"]
        result["listener_arn"] = listener["ListenerArn"]

        if any(other is not desired and listeners_overlap(current, other) for other in desired_changes):
            wait_for_accelerator(
                client, module, accelerator_arn, "accelerator_deployed", changed=True, deadline=deadline
            )

    for index, desired in enumerate(creates):
        # Predict the AWS creation default when client_affinity is omitted.
        result = {
            "client_affinity": desired["client_affinity"] or "NONE",
            "port_ranges": desired["port_ranges"],
            "protocol": desired["protocol"],
        }

        if module.check_mode:
            result_listeners.append((result, desired, True))
            continue

        request = create_requests[index]
        while True:
            try:
                response = client.create_listener(
                    **request,
                    aws_retry=True,
                )
                listener = validate_listener(
                    module,
                    response.get("Listener") if isinstance(response, dict) else None,
                    changed=True,
                )
                break
            except is_boto3_error_code("LimitExceededException") as e:
                if not deletes:
                    module.fail_json_aws(
                        e,
                        changed=mutated,
                        msg=f"Unable to create AWS Global Accelerator listener for {accelerator_arn}",
                    )

                current = deletes.pop(0)
                delete_listener(
                    client, module, accelerator_arn, current["listener_arn"], changed=mutated, deadline=deadline
                )
                mutated = True
                wait_for_accelerator(
                    client, module, accelerator_arn, "accelerator_deployed", changed=True, deadline=deadline
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    changed=mutated,
                    msg=f"Unable to create AWS Global Accelerator listener for {accelerator_arn}",
                )

        mutated = True
        result["client_affinity"] = listener["ClientAffinity"]
        result["listener_arn"] = listener["ListenerArn"]
        result_listeners.append((result, desired, True))

    if not module.check_mode:
        for current in deletes:
            delete_listener(
                client, module, accelerator_arn, current["listener_arn"], changed=mutated, deadline=deadline
            )
            mutated = True

    if (
        changed
        and not module.check_mode
        and any(item[1] and item[1]["endpoint_groups"] is not None for item in result_listeners)
    ):
        wait_for_accelerator(client, module, accelerator_arn, "accelerator_deployed", changed=True, deadline=deadline)

    results = []
    for result, desired, port_ranges_sent in result_listeners:
        if desired is not None and desired["endpoint_groups"] is not None:
            # AWS checks health on the first port of the listener's ranges in the order it stores them, which is the
            # order they were sent in. get_listeners sorts listed ranges, so an unchanged listener's order is known
            # only for a single range.
            default_health_check_port = None
            if port_ranges_sent or len(result["port_ranges"]) == 1:
                default_health_check_port = result["port_ranges"][0]["from_port"]

            endpoint_groups_changed, endpoint_groups = ensure_endpoint_groups(
                client,
                module,
                result.get("listener_arn"),
                desired["endpoint_groups"],
                mutated=mutated,
                default_health_check_port=default_health_check_port,
            )
            changed = changed or endpoint_groups_changed
            mutated = mutated or (endpoint_groups_changed and not module.check_mode)
            result["endpoint_groups"] = endpoint_groups

        results.append(result)

    results = sorted(results, key=listener_identity)
    return changed, results


def ensure_absent(client, module):
    # Every wait in one run shares wait_timeout.
    deadline = wait_deadline(module)
    accelerator = get_accelerator(client, module)
    changed = accelerator is not None

    if changed and not module.check_mode:
        accelerator_arn = accelerator["AcceleratorArn"]
        if accelerator.get("Status") and accelerator.get("Status") != "DEPLOYED":
            wait_for_accelerator(client, module, accelerator_arn, "accelerator_deployed_or_deleted", deadline=deadline)
            accelerator = get_accelerator_by_arn(client, module, accelerator_arn)
            if accelerator is None:
                # The accelerator disappeared before this module modified anything.
                module.exit_json(changed=False, state="absent")

        listeners = get_listeners(client, module, accelerator_arn)

        accelerator_methods = {"delete_accelerator": ("AcceleratorArn",)}
        if accelerator.get("Enabled"):
            accelerator_methods["update_accelerator"] = ("AcceleratorArn", "Enabled")

        require_client_methods(module, client, "Global Accelerator", accelerator_methods)

        # Failures after the first deletion report changed=True.
        mutated = False
        for listener in listeners:
            delete_listener(
                client, module, accelerator_arn, listener["listener_arn"], changed=mutated, deadline=deadline
            )
            mutated = True

        if listeners:
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deployed",
                changed=True,
                deadline=deadline,
            )

        if accelerator.get("Enabled"):
            try:
                client.update_accelerator(
                    AcceleratorArn=accelerator_arn,
                    Enabled=False,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    changed=mutated,
                    msg=f"Unable to disable AWS Global Accelerator {accelerator_arn}",
                )

            mutated = True
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deployed",
                changed=True,
                deadline=deadline,
            )

        try:
            client.delete_accelerator(
                AcceleratorArn=accelerator_arn,
                aws_retry=True,
            )
        except is_boto3_error_code("AcceleratorNotFoundException"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=mutated, msg=f"Unable to delete AWS Global Accelerator {accelerator_arn}")

        if module.params["wait"]:
            wait_for_accelerator(
                client,
                module,
                accelerator_arn,
                "accelerator_deleted",
                changed=True,
                deadline=deadline,
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module, deadline=None):
    # Every wait in one run, including the one before the accelerator is checked again, shares wait_timeout.
    if deadline is None:
        deadline = wait_deadline(module)

    tags = module.params["tags"]
    ip_addresses = module.params["ip_addresses"] or None
    desired = scrub_none_parameters(
        {
            "enabled": module.params["enabled"],
            "ip_address_type": module.params["ip_address_type"],
            "name": module.params["name"],
        }
    )

    if ip_addresses is not None:
        desired["ip_addresses"] = sorted(ip_addresses)

    accelerator = get_accelerator(client, module)
    if accelerator is None and module.params.get("arn") is not None:
        module.fail_json(msg=f"AWS Global Accelerator {module.params['arn']} does not exist")

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
        current_tags = boto3_tag_list_to_ansible_dict(list_accelerator_tags(client, module, accelerator_arn))

    current = None
    if accelerator is not None:
        current = {
            field: value
            for field, value in (
                ("enabled", accelerator.get("Enabled")),
                ("ip_address_type", accelerator.get("IpAddressType")),
                ("name", accelerator.get("Name")),
            )
            if field in desired
        }

        if ip_addresses is not None:
            current["ip_addresses"] = sorted(
                address
                for ip_set in accelerator.get("IpSets", [])
                for address in ip_set["IpAddresses"]
                if address in ip_addresses
            )
            if current["ip_addresses"] != desired["ip_addresses"]:
                module.fail_json(
                    msg=(
                        "ip_addresses cannot be changed for existing AWS Global Accelerator "
                        f"{accelerator['AcceleratorArn']}. The existing accelerator has not been modified."
                    )
                )

    resource_changed = current != desired

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current_tags,
            tags,
            purge_tags=module.params["purge_tags"],
        )
        require_resulting_tag_limit(module, current_tags, tags_to_set, tag_keys_to_unset, 50, "accelerator")

    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if (
        accelerator is not None
        and not module.check_mode
        and (changed or module.params["listeners"] is not None or module.params["wait"])
        and accelerator.get("Status")
        and accelerator.get("Status") != "DEPLOYED"
    ):
        wait_for_accelerator(
            client,
            module,
            accelerator["AcceleratorArn"],
            "accelerator_deployed",
            deadline=deadline,
        )
        return ensure_present(client, module, deadline=deadline)

    if not module.check_mode:
        # Later writes are checked before the first change, so an older botocore fails without modifying anything.
        tag_methods = {}
        if not created and tag_keys_to_unset:
            tag_methods["untag_resource"] = ("ResourceArn", "TagKeys")

        if not created and tags_to_set:
            tag_methods["tag_resource"] = ("ResourceArn", "Tags")

        if tag_methods:
            require_client_methods(module, client, "Global Accelerator", tag_methods)

        if module.params["listeners"] is not None:
            require_listener_writes(module, client)
            require_endpoint_group_writes(module, client)

    if created and not module.check_mode:
        # A fixed token would replay an earlier create, even one renamed since; AWSRetry reuses this one.
        token = module.params["idempotency_token"]
        if token is None:
            token = str(uuid.uuid4())

        request = scrub_none_parameters(
            snake_dict_to_camel_dict(
                {
                    "enabled": desired.get("enabled"),
                    "idempotency_token": token,
                    "ip_addresses": ip_addresses,
                    "ip_address_type": desired.get("ip_address_type"),
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
            response = client.create_accelerator(
                **request,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Global Accelerator {desired['name']}",
            )

        accelerator = validate_accelerator(
            module,
            response.get("Accelerator") if isinstance(response, dict) else None,
            changed=True,
        )
    elif created and module.check_mode:
        # Predict the AWS creation defaults for omitted settings and the status a real run returns after waiting.
        accelerator = {
            "Enabled": desired.get("enabled", True),
            "IpAddressType": desired.get("ip_address_type", "IPV4"),
            "Name": desired["name"],
            "Status": "DEPLOYED" if module.params["wait"] else "IN_PROGRESS",
        }
        if ip_addresses is not None:
            accelerator["IpSets"] = [{"IpAddresses": ip_addresses}]
    elif resource_changed and not module.check_mode:
        request = scrub_none_parameters(
            snake_dict_to_camel_dict(
                {
                    "accelerator_arn": accelerator["AcceleratorArn"],
                    "enabled": desired.get("enabled"),
                    "ip_address_type": desired.get("ip_address_type"),
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
            response = client.update_accelerator(
                **request,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to update AWS Global Accelerator {request['AcceleratorArn']}",
            )

        accelerator = validate_accelerator(
            module,
            response.get("Accelerator") if isinstance(response, dict) else None,
            expected_arn=request["AcceleratorArn"],
            changed=True,
        )
    elif resource_changed and module.check_mode:
        accelerator = dict(accelerator)
        # Without a wait, a real run returns the UpdateAccelerator response, which reports the change deploying.
        if not module.params["wait"]:
            accelerator["Status"] = "IN_PROGRESS"

        accelerator["Name"] = desired["name"]
        if "enabled" in desired:
            accelerator["Enabled"] = desired["enabled"]

        if "ip_address_type" in desired:
            accelerator["IpAddressType"] = desired["ip_address_type"]

    # Failures after the accelerator was created or updated report changed=True.
    mutated = not module.check_mode and (created or resource_changed)
    listeners = None
    listeners_changed = False
    if module.params["listeners"] is not None:
        if created and module.params["listeners"] and not module.check_mode:
            wait_for_accelerator(
                client,
                module,
                accelerator["AcceleratorArn"],
                "accelerator_deployed",
                changed=True,
                deadline=deadline,
            )

        listeners_changed, listeners = ensure_listeners(
            client,
            module,
            accelerator.get("AcceleratorArn"),
            mutated=mutated,
            deadline=deadline,
        )
        changed = changed or listeners_changed
        mutated = mutated or (listeners_changed and not module.check_mode)

    if module.params["wait"] and not module.check_mode and mutated:
        accelerator_arn = accelerator["AcceleratorArn"]
        wait_for_accelerator(
            client,
            module,
            accelerator_arn,
            "accelerator_deployed",
            changed=True,
            deadline=deadline,
        )
        accelerator = get_accelerator_by_arn(client, module, accelerator_arn, changed=True)
        if accelerator is None:
            module.fail_json(changed=True, msg=f"AWS Global Accelerator {accelerator_arn} disappeared after update")

    if tags is not None:
        if not created and not module.check_mode:
            reconcile_arn_tags(
                module,
                client,
                accelerator["AcceleratorArn"],
                tags_to_set,
                tag_keys_to_unset,
                "AWS Global Accelerator",
                changed=mutated,
            )

        accelerator = dict(accelerator)
        accelerator["Tags"] = ansible_dict_to_boto3_tag_list(updated_tags(current_tags, tags_to_set, tag_keys_to_unset))

    result_accelerator = boto3_resource_to_ansible_dict(accelerator, transform_tags=True, force_tags=False)
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
            "enabled": {"type": "bool"},
            "idempotency_token": {"no_log": False, "type": "str"},
            "ip_addresses": {"elements": "str", "type": "list"},
            "ip_address_type": {
                "choices": ["DUAL_STACK", "IPV4"],
                "type": "str",
            },
            "listeners": {
                "elements": "dict",
                "options": {
                    "client_affinity": {
                        "choices": ["NONE", "SOURCE_IP"],
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
            "tags": {"aliases": ["resource_tags"], "type": "dict"},
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 10, "type": "int"},
            "wait_timeout": {"default": 600, "type": "int"},
        },
        required_if=[("state", "present", ["name"])],
        required_one_of=[["arn", "name"]],
        supports_check_mode=True,
    )

    state = module.params["state"]
    require_positive_wait_bounds(module, always=True)

    if len(module.params.get("name") or "") > 255:
        module.fail_json(msg="name must contain at most 255 characters")

    if state == "present":
        ip_addresses = module.params["ip_addresses"] or []
        listeners = module.params["listeners"] or []
        if len(module.params.get("idempotency_token") or "") > 255:
            module.fail_json(msg="idempotency_token must contain at most 255 characters")

        if len(ip_addresses) > 2:
            module.fail_json(msg="ip_addresses must contain at most 2 entries")

        if any(len(address) > 45 for address in ip_addresses):
            module.fail_json(msg="ip_addresses entries must contain at most 45 characters")

        for address in ip_addresses:
            try:
                ipaddress.IPv4Address(address)
            except ipaddress.AddressValueError:
                module.fail_json(msg=f"ip_addresses entries must be valid IPv4 addresses: {address}")

        if len(set(ip_addresses)) != len(ip_addresses):
            module.fail_json(msg="ip_addresses entries must be unique")

        listener_port_ranges = {}
        if sum(len(listener.get("endpoint_groups") or []) for listener in listeners) > 42:
            module.fail_json(msg="listeners must contain at most 42 endpoint groups in total")

        for listener in listeners:
            if not listener["port_ranges"]:
                module.fail_json(msg="listeners entries require at least one port_ranges entry")

            if len(listener["port_ranges"]) > 10:
                module.fail_json(msg="listeners entries allow at most 10 port_ranges entries")

            for port_range in listener["port_ranges"]:
                if port_range["from_port"] < 1 or port_range["to_port"] > 65535:
                    module.fail_json(msg="port_ranges entries must be between 1 and 65535")

                if port_range["from_port"] > port_range["to_port"]:
                    module.fail_json(msg="port_ranges entries require from_port to be less than or equal to to_port")

            ordered_port_ranges = normalized_port_ranges(listener["port_ranges"])
            protocol_port_ranges = listener_port_ranges.setdefault(listener.get("protocol"), [])
            for port_range in ordered_port_ranges:
                if any(port_ranges_overlap(port_range, current) for current in protocol_port_ranges):
                    module.fail_json(msg="listeners port_ranges entries must not overlap")

                protocol_port_ranges.append(port_range)

            regions = set()
            for endpoint_group in listener.get("endpoint_groups") or []:
                region = endpoint_group["endpoint_group_region"]

                # Ansible turns a null required string into "", which AWS would only reject after earlier changes.
                if not region:
                    module.fail_json(msg="endpoint_group_region must not be empty")

                if len(region) > 255:
                    module.fail_json(msg="endpoint_group_region must contain at most 255 characters")

                if region in regions:
                    module.fail_json(msg=f"Duplicate endpoint group region {region} in endpoint_groups")

                regions.add(region)

                if len(endpoint_group.get("endpoint_configurations") or []) > 10:
                    module.fail_json(
                        msg=f"Endpoint group {region} endpoint_configurations must contain at most 10 entries"
                    )

                if len(endpoint_group.get("port_overrides") or []) > 10:
                    module.fail_json(msg=f"Endpoint group {region} port_overrides must contain at most 10 entries")

                if endpoint_group.get("health_check_port") is not None and not (
                    1 <= endpoint_group["health_check_port"] <= 65535
                ):
                    module.fail_json(msg=f"Endpoint group {region} health_check_port must be between 1 and 65535")

                health_check_path = endpoint_group.get("health_check_path")
                if health_check_path is not None and (
                    len(health_check_path) > 255
                    or re.fullmatch(r"/[-a-zA-Z0-9@:%_+.~#?&/=]*", health_check_path) is None
                ):
                    module.fail_json(
                        msg=f"Endpoint group {region} health_check_path must be a valid path of at most 255 characters"
                    )

                if endpoint_group.get("threshold_count") is not None and not (
                    1 <= endpoint_group["threshold_count"] <= 10
                ):
                    module.fail_json(msg=f"Endpoint group {region} threshold_count must be between 1 and 10")

                if endpoint_group.get("traffic_dial_percentage") is not None and not (
                    0 <= endpoint_group["traffic_dial_percentage"] <= 100
                ):
                    module.fail_json(msg=f"Endpoint group {region} traffic_dial_percentage must be between 0 and 100")

                endpoint_ids = set()
                for configuration in endpoint_group.get("endpoint_configurations") or []:
                    endpoint_id = configuration["endpoint_id"]
                    if not endpoint_id:
                        module.fail_json(msg=f"Endpoint group {region} endpoint_id must not be empty")

                    if len(endpoint_id) > 255 or len(configuration.get("attachment_arn") or "") > 255:
                        module.fail_json(
                            msg=(
                                f"Endpoint group {region} endpoint IDs and attachment "
                                "ARNs must contain at most 255 characters"
                            )
                        )

                    if endpoint_id in endpoint_ids:
                        module.fail_json(
                            msg=f"Duplicate endpoint {endpoint_id} in endpoint group {region} endpoint_configurations"
                        )

                    endpoint_ids.add(endpoint_id)

                    if not 0 <= configuration["weight"] <= 255:
                        module.fail_json(
                            msg=f"Endpoint group {region} endpoint_configurations weight must be between 0 and 255"
                        )

                override_listener_ports = set()
                for port_override in endpoint_group.get("port_overrides") or []:
                    if not (
                        1 <= port_override["listener_port"] <= 65535 and 1 <= port_override["endpoint_port"] <= 65535
                    ):
                        module.fail_json(
                            msg=f"Endpoint group {region} port_overrides entries must be between 1 and 65535"
                        )

                    if port_override["listener_port"] in override_listener_ports:
                        module.fail_json(
                            msg=f"Endpoint group {region} port_overrides listener_port values must be unique"
                        )

                    override_listener_ports.add(port_override["listener_port"])

        require_valid_tags(module, module.params["tags"], 50)

    # Some ansible-core versions let an explicit null past required_if and required_one_of; fail as if it were omitted.
    if module.params.get("arn") is None and module.params.get("name") is None:
        module.fail_json(msg="one of the following is required: arn, name")

    if state == "present" and module.params.get("name") is None:
        module.fail_json(msg="state is present but all of the following are missing: name")

    client = module.client(
        "globalaccelerator",
        region="us-west-2",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["TransactionInProgressException"]),
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
