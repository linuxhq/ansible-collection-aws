#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver
version_added: 1.9.1
short_description: Manage AWS Route53 Resolver endpoints
description:
  - Manages AWS Route53 Resolver endpoints.
  - Compares the desired endpoint settings against the current endpoint fetched by name.
  - O(direction) and O(security_group_ids) are immutable after creation.
author:
  - Taylor Kimball (@tkimball83)
options:
  direction:
    description:
      - The resolver endpoint direction.
      - This is required when O(state=present).
    choices:
      - inbound
      - outbound
    type: str
  ip_addresses:
    description:
      - The resolver endpoint IP address definitions.
      - This is required when O(state=present).
    elements: dict
    suboptions:
      ip:
        description:
          - The IPv4 address for the endpoint.
        type: str
      ipv6:
        description:
          - The IPv6 address for the endpoint.
        type: str
      subnet_id:
        description:
          - The subnet ID for the endpoint IP address.
        required: true
        type: str
    type: list
  name:
    description:
      - The resolver endpoint name.
    required: true
    type: str
  protocols:
    description:
      - The protocols for the resolver endpoint.
    choices:
      - do53
      - doh
      - doh-fips
    default:
      - do53
    elements: str
    type: list
  resolver_endpoint_type:
    description:
      - The resolver endpoint type.
    choices:
      - ipv4
      - dualstack
    default: ipv4
    type: str
  security_group_ids:
    description:
      - The security group IDs for the resolver endpoint.
      - This is required when O(state=present).
    elements: str
    type: list
  state:
    description:
      - Whether the resolver endpoint should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  wait:
    description:
      - Whether to wait for the resolver endpoint state change to complete.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
    default: 300
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a Route53 Resolver endpoint is present
  linuxhq.aws.route53_resolver:
    direction: outbound
    ip_addresses:
      - subnet_id: subnet-0123456789abcdef0
        ip: 192.168.0.125
      - subnet_id: subnet-0123456789abcdef1
        ip: 192.168.0.253
    name: molecule
    protocols:
      - do53
      - doh
    security_group_ids:
      - sg-0123456789abcdef0

- name: Ensure a Route53 Resolver endpoint is absent
  linuxhq.aws.route53_resolver:
    name: molecule
    state: absent
"""

RETURN = r"""
resolver_endpoint:
  description:
    - The current resolver endpoint after module execution.
  returned: when state is present
  type: dict
resolver_endpoint_id:
  description:
    - The resolver endpoint ID.
  returned: when a resolver endpoint exists after module execution
  type: str
name:
  description:
    - The requested resolver endpoint name.
  returned: always
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_list_to_snake_dicts,
    aws_resource_to_snake_dict,
    canonicalize_list,
    find_aws_resource,
    list_difference,
    validated_field_differences,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    wait_for_aws_resource,
)

ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA = {
    "resolver_endpoint_operational": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverEndpoint",
        "acceptors": [
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "OPERATIONAL",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "CREATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "UPDATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "AUTO_RECOVERING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "ACTION_NEEDED",
                "matcher": "path",
                "state": "failure",
            },
        ],
    },
    "resolver_endpoint_deleted": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverEndpoint",
        "acceptors": [
            {
                "expected": "ResourceNotFoundException",
                "matcher": "error",
                "state": "success",
            },
            {
                "argument": "ResolverEndpoint.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}

IMMUTABLE_ITEMS = ["direction", "security_group_ids"]
COMPARE_ITEMS = [
    "direction",
    "ip_addresses",
    "protocols",
    "resolver_endpoint_type",
    "security_group_ids",
]
PROTOCOLS = {
    "do53": "Do53",
    "doh": "DoH",
    "doh-fips": "DoH-FIPS",
}


def aws_ip_address(ip_address):
    return scrub_none_parameters(
        {
            "Ip": ip_address.get("ip"),
            "Ipv6": ip_address.get("ipv6"),
            "SubnetId": ip_address.get("subnet_id"),
        }
    )


def aws_ip_addresses(ip_addresses):
    return [aws_ip_address(ip_address) for ip_address in ip_addresses]


def aws_ip_address_update(ip_address):
    return scrub_none_parameters(
        {
            "Ip": ip_address.get("ip"),
            "IpId": ip_address.get("ip_id"),
            "Ipv6": ip_address.get("ipv6"),
            "SubnetId": ip_address.get("subnet_id"),
        }
    )


def aws_protocols(protocols):
    return [PROTOCOLS[protocol.lower()] for protocol in protocols or []]


def build_desired_resolver_endpoint(module):
    return {
        "direction": module.params["direction"].upper(),
        "ip_addresses": module.params["ip_addresses"],
        "name": module.params["name"],
        "protocols": aws_protocols(module.params["protocols"]),
        "resolver_endpoint_type": module.params["resolver_endpoint_type"].upper(),
        "security_group_ids": module.params["security_group_ids"],
    }


def normalize_ip_address(ip_address):
    return scrub_none_parameters(
        {
            "ip": ip_address.get("ip"),
            "ipv6": ip_address.get("ipv6"),
            "subnet_id": ip_address.get("subnet_id"),
        }
    )


def ip_address_sort_key(ip_address):
    return (
        ip_address.get("subnet_id") or "",
        ip_address.get("ip") or "",
        ip_address.get("ipv6") or "",
    )


def normalize_ip_addresses(ip_addresses):
    return canonicalize_list(
        ip_addresses,
        normalize_ip_address,
        ip_address_sort_key,
    )


def ip_addresses_equal(current_ip_addresses, desired_ip_addresses):
    return normalize_ip_addresses(current_ip_addresses) == normalize_ip_addresses(
        desired_ip_addresses
    )


def normalize_protocols(protocols):
    return sorted(protocol.lower() for protocol in protocols or ["Do53"])


def comparable_resolver_endpoint(endpoint, desired=None):
    if not endpoint:
        return None

    comparable = {
        "direction": endpoint.get("direction"),
        "ip_addresses": normalize_ip_addresses(endpoint.get("ip_addresses", [])),
        "protocols": normalize_protocols(endpoint.get("protocols")),
        "resolver_endpoint_type": endpoint.get("resolver_endpoint_type"),
        "security_group_ids": sorted(endpoint.get("security_group_ids", [])),
    }

    if desired is not None and ip_addresses_equal(
        comparable["ip_addresses"],
        desired["ip_addresses"],
    ):
        comparable["ip_addresses"] = normalize_ip_addresses(desired["ip_addresses"])

    return comparable


def comparable_desired_resolver_endpoint(desired):
    return {
        "direction": desired["direction"],
        "ip_addresses": normalize_ip_addresses(desired["ip_addresses"]),
        "protocols": normalize_protocols(desired["protocols"]),
        "resolver_endpoint_type": desired["resolver_endpoint_type"],
        "security_group_ids": sorted(desired["security_group_ids"]),
    }


def normalize_resolver_endpoint_with_ip_addresses(client, module, endpoint):
    normalized = aws_resource_to_snake_dict(endpoint)
    if endpoint is None or endpoint.get("Id") is None:
        return normalized

    normalized["ip_addresses"] = aws_resource_list_to_snake_dicts(
        aws_paginated_list(
            client,
            module,
            "list_resolver_endpoint_ip_addresses",
            "IpAddresses",
            ResolverEndpointId=endpoint["Id"],
        )
    )
    return normalized


def get_resolver_endpoint(client, module, resolver_endpoint_id):
    return aws_resource(
        client,
        module,
        "get_resolver_endpoint",
        "ResolverEndpoint",
        ignore_error_codes="ResourceNotFoundException",
        ignored_error_result=None,
        ResolverEndpointId=resolver_endpoint_id,
    )


def get_resolver_endpoint_by_name(client, module, name):
    return find_aws_resource(
        aws_paginated_list(
            client,
            module,
            "list_resolver_endpoints",
            "ResolverEndpoints",
        ),
        name=name,
    )


def wait_for_resolver_endpoint_status(
    client, module, resolver_endpoint_id, statuses, name
):
    deleted = "deleted" in statuses
    wait_for_aws_resource(
        client,
        module,
        ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA,
        "resolver_endpoint_deleted" if deleted else "resolver_endpoint_operational",
        f"Timed out waiting for AWS Route53 Resolver endpoint {name}",
        ResolverEndpointId=resolver_endpoint_id,
    )
    if deleted:
        return None
    return get_resolver_endpoint(client, module, resolver_endpoint_id)


def create_resolver_endpoint(client, module, desired):
    response = aws_response(
        client,
        module,
        "create_resolver_endpoint",
        error_message=f"Unable to create AWS Route53 Resolver endpoint {desired['name']}",
        CreatorRequestId=desired["name"],
        Direction=desired["direction"],
        IpAddresses=aws_ip_addresses(desired["ip_addresses"]),
        Name=desired["name"],
        Protocols=desired["protocols"],
        ResolverEndpointType=desired["resolver_endpoint_type"],
        SecurityGroupIds=desired["security_group_ids"],
    )
    endpoint = response.get("ResolverEndpoint")
    if module.params["wait"]:
        endpoint = wait_for_resolver_endpoint_status(
            client, module, endpoint["Id"], {"operational"}, desired["name"]
        )
    return endpoint


def update_resolver_endpoint_config(client, module, endpoint, differences, desired):
    update_params = {"ResolverEndpointId": endpoint["id"]}
    if "protocols" in differences:
        update_params["Protocols"] = desired["protocols"]
    if "resolver_endpoint_type" in differences:
        update_params["ResolverEndpointType"] = desired["resolver_endpoint_type"]

    response = aws_response(
        client,
        module,
        "update_resolver_endpoint",
        error_message=f"Unable to update AWS Route53 Resolver endpoint {desired['name']}",
        **update_params,
    )
    endpoint = response.get("ResolverEndpoint")
    if module.params["wait"]:
        endpoint = wait_for_resolver_endpoint_status(
            client, module, endpoint["Id"], {"operational"}, desired["name"]
        )
    return endpoint


def reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired):
    resolver_endpoint_id = endpoint["id"]
    current_ip_addresses = endpoint.get("ip_addresses", [])
    desired_ip_addresses = desired["ip_addresses"]
    ip_addresses_to_add = list_difference(
        desired_ip_addresses,
        current_ip_addresses,
        normalize_ip_address,
        ip_address_sort_key,
    )
    ip_addresses_to_remove = list_difference(
        current_ip_addresses,
        desired_ip_addresses,
        normalize_ip_address,
        ip_address_sort_key,
    )

    for ip_address in ip_addresses_to_add:
        aws_response(
            client,
            module,
            "associate_resolver_endpoint_ip_address",
            error_message=(
                "Unable to reconcile AWS Route53 Resolver endpoint IP addresses "
                f"for {desired['name']}"
            ),
            ResolverEndpointId=resolver_endpoint_id,
            IpAddress=aws_ip_address_update(ip_address),
        )
        if module.params["wait"]:
            wait_for_resolver_endpoint_status(
                client,
                module,
                resolver_endpoint_id,
                {"operational"},
                desired["name"],
            )

    for ip_address in ip_addresses_to_remove:
        aws_response(
            client,
            module,
            "disassociate_resolver_endpoint_ip_address",
            error_message=(
                "Unable to reconcile AWS Route53 Resolver endpoint IP addresses "
                f"for {desired['name']}"
            ),
            ResolverEndpointId=resolver_endpoint_id,
            IpAddress=aws_ip_address_update(ip_address),
        )
        if module.params["wait"]:
            wait_for_resolver_endpoint_status(
                client,
                module,
                resolver_endpoint_id,
                {"operational"},
                desired["name"],
            )

    return normalize_resolver_endpoint_with_ip_addresses(
        client,
        module,
        get_resolver_endpoint(client, module, resolver_endpoint_id),
    )


def update_resolver_endpoint(client, module, endpoint, differences, desired):
    if "protocols" in differences or "resolver_endpoint_type" in differences:
        endpoint = normalize_resolver_endpoint_with_ip_addresses(
            client,
            module,
            update_resolver_endpoint_config(
                client,
                module,
                endpoint,
                differences,
                desired,
            ),
        )

    if "ip_addresses" in differences:
        endpoint = reconcile_resolver_endpoint_ip_addresses(
            client,
            module,
            endpoint,
            desired,
        )

    return endpoint


def ensure_present(client, module):
    desired = build_desired_resolver_endpoint(module)
    endpoint = get_resolver_endpoint_by_name(client, module, desired["name"])
    if endpoint is not None:
        endpoint = normalize_resolver_endpoint_with_ip_addresses(
            client, module, endpoint
        )

    current = comparable_resolver_endpoint(endpoint, desired)
    desired_comparable = comparable_desired_resolver_endpoint(desired)
    if current is None:
        changed = True
    else:
        differences, changed = validated_field_differences(
            module,
            current,
            desired_comparable,
            COMPARE_ITEMS,
            IMMUTABLE_ITEMS,
            (
                "Unable to update AWS Route53 Resolver endpoint "
                f"{module.params['name']}: immutable fields differ"
            ),
        )

    if current is None and not module.check_mode:
        endpoint = normalize_resolver_endpoint_with_ip_addresses(
            client,
            module,
            create_resolver_endpoint(client, module, desired),
        )
    elif current is None and module.check_mode:
        endpoint = desired
    elif changed and not module.check_mode:
        endpoint = update_resolver_endpoint(
            client,
            module,
            endpoint,
            differences,
            desired,
        )
    elif changed and module.check_mode:
        endpoint = desired

    result = {
        "changed": changed,
        "name": desired["name"],
        "resolver_endpoint": endpoint,
        "state": "present",
    }
    if endpoint is not None and endpoint.get("id") is not None:
        result["resolver_endpoint_id"] = endpoint["id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module, module.params["name"])
    changed = endpoint is not None

    if changed and not module.check_mode:
        resolver_endpoint_id = endpoint["Id"]
        aws_response(
            client,
            module,
            "delete_resolver_endpoint",
            error_message=(
                "Unable to delete AWS Route53 Resolver endpoint "
                f"{module.params['name']}"
            ),
            ResolverEndpointId=resolver_endpoint_id,
        )
        if module.params["wait"]:
            wait_for_resolver_endpoint_status(
                client,
                module,
                resolver_endpoint_id,
                {"deleted"},
                module.params["name"],
            )

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "direction": {
                "choices": ["inbound", "outbound"],
                "type": "str",
            },
            "ip_addresses": {
                "elements": "dict",
                "options": {
                    "ip": {"type": "str"},
                    "ipv6": {"type": "str"},
                    "subnet_id": {"required": True, "type": "str"},
                },
                "type": "list",
            },
            "name": {"required": True, "type": "str"},
            "protocols": {
                "choices": ["do53", "doh", "doh-fips"],
                "default": ["do53"],
                "elements": "str",
                "type": "list",
            },
            "resolver_endpoint_type": {
                "choices": ["ipv4", "dualstack"],
                "default": "ipv4",
                "type": "str",
            },
            "security_group_ids": {
                "elements": "str",
                "type": "list",
            },
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 5, "type": "int"},
            "wait_timeout": {"default": 300, "type": "int"},
        },
        required_if=[
            ("state", "present", ["direction", "ip_addresses", "security_group_ids"]),
        ],
        supports_check_mode=True,
    )
    client = module.client("route53resolver")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
