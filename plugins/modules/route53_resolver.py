#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver
short_description: Manage aws route53 resolver endpoints
description:
  - Manages AWS Route53 Resolver endpoints.
  - Compares the desired endpoint settings against the current endpoint fetched by name.
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
      - This must contain 2 to 20 entries.
    elements: dict
    suboptions:
      ip:
        description:
          - The IPv4 address for the endpoint.
          - Mutually exclusive with O(ip_addresses[].ipv6).
        type: str
      ipv6:
        description:
          - The IPv6 address for the endpoint.
          - Mutually exclusive with O(ip_addresses[].ip).
        type: str
      subnet_id:
        description:
          - The subnet ID for the endpoint IP address.
          - This must contain 1 to 32 characters.
        required: true
        type: str
    type: list
  name:
    description:
      - The resolver endpoint name.
      - This must be a nonnumeric name of at most 64 letters, numbers, spaces,
        apostrophes, hyphens, or underscores.
    required: true
    type: str
  protocols:
    description:
      - The protocols for the resolver endpoint.
      - This must contain 1 or 2 entries.
    choices:
      - do53
      - doh
      - doh-fips
    default:
      - do53
    elements: str
    type: list
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  resolver_endpoint_type:
    description:
      - The resolver endpoint type.
    choices:
      - dualstack
      - ipv4
      - ipv6
    default: ipv4
    type: str
  security_group_ids:
    description:
      - The security group IDs for the resolver endpoint.
      - This is required when O(state=present).
      - Entries must contain 1 to 64 characters.
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
  tags:
    description:
      - Tags to apply to the resolver endpoint.
      - This must contain at most 200 entries; keys must contain 1 to 128
        characters and values at most 256 characters.
    type: dict
  wait:
    description:
      - Whether to wait for the resolver endpoint state change to complete.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    default: 300
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Ensure a Route53 Resolver endpoint is present
  linuxhq.aws.route53_resolver:
    direction: outbound
    ip_addresses:
      - ip: 192.168.0.125
        subnet_id: subnet-0123456789abcdef0
      - ip: 192.168.0.253
        subnet_id: subnet-0123456789abcdef1
    name: molecule
    protocols:
      - do53
      - doh
    security_group_ids:
      - sg-0123456789abcdef0
    tags:
      Name: molecule

- name: Ensure a Route53 Resolver endpoint is absent
  linuxhq.aws.route53_resolver:
    name: molecule
    state: absent
"""

RETURN = r"""
name:
  description:
    - The requested resolver endpoint name.
  returned: always
  type: str
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
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
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

IP_ADDRESS_COMPARISON_FIELDS = ("ip", "ipv6", "subnet_id")
IP_ADDRESS_REQUEST_FIELDS = ("ip", "ip_id", "ipv6", "subnet_id")
PROTOCOLS = {
    "do53": "Do53",
    "doh": "DoH",
    "doh-fips": "DoH-FIPS",
}


def create_resolver_endpoint(client, module, desired):
    try:
        response = client.create_resolver_endpoint(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "creator_request_id": hashlib.sha256(json.dumps(desired, sort_keys=True).encode()).hexdigest(),
                        "direction": desired["direction"],
                        "ip_addresses": desired["ip_addresses"],
                        "name": desired["name"],
                        "protocols": desired["protocols"],
                        "resolver_endpoint_type": desired["resolver_endpoint_type"],
                        "security_group_ids": desired["security_group_ids"],
                        "tags": (
                            ansible_dict_to_boto3_tag_list(module.params["tags"])
                            if module.params["tags"] is not None
                            else None
                        ),
                    },
                    capitalize_first=True,
                )
            ),
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to create AWS Route53 Resolver endpoint {desired['name']}",
        )

    endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
    if not isinstance(endpoint, dict) or not endpoint.get("Id"):
        endpoint = get_resolver_endpoint_by_name(client, module)
    if endpoint is None:
        module.fail_json(msg=("AWS Route53 Resolver did not return the created endpoint " f"{desired['name']}"))
    endpoint = validate_resolver_endpoint(module, endpoint, "create_resolver_endpoint")

    if module.params["wait"]:
        resolver_endpoint_id = endpoint.get("Id")
        endpoint = wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            {"operational"},
        )
    elif endpoint is not None:
        endpoint = dict(endpoint)
        endpoint["IpAddresses"] = [
            snake_dict_to_camel_dict(ip_address, capitalize_first=True) for ip_address in desired["ip_addresses"]
        ]
        if module.params["tags"] is not None:
            endpoint["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
    return endpoint


def delete_resolver_endpoint(client, module, endpoint, always=False):
    resolver_endpoint_id = endpoint.get("Id")

    try:
        client.delete_resolver_endpoint(
            ResolverEndpointId=resolver_endpoint_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=("Unable to delete AWS Route53 Resolver endpoint " f"{module.params['name']}"),
        )

    if module.params["wait"] or always:
        wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            {"deleted"},
        )


def ensure_absent(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module)
    deleting = (endpoint or {}).get("Status") == "DELETING"
    changed = endpoint is not None and not deleting

    if deleting and module.params["wait"] and not module.check_mode:
        wait_for_resolver_endpoint_status(client, module, endpoint.get("Id"), {"deleted"})
    elif changed and not module.check_mode:
        delete_resolver_endpoint(client, module, endpoint)

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    desired = {
        "direction": module.params["direction"].upper(),
        "ip_addresses": module.params["ip_addresses"],
        "name": module.params["name"],
        "protocols": sorted({PROTOCOLS[protocol.lower()] for protocol in module.params["protocols"] or []}),
        "resolver_endpoint_type": module.params["resolver_endpoint_type"].upper(),
        "security_group_ids": sorted(set(module.params["security_group_ids"])),
    }
    endpoint = get_resolver_endpoint_by_name(client, module)

    if endpoint is not None:
        if endpoint.get("Status") == "DELETING":
            if module.check_mode:
                endpoint = None
            else:
                wait_for_resolver_endpoint_status(client, module, endpoint.get("Id"), {"deleted"})
                return ensure_present(client, module)
        else:
            endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint)
            endpoint = resolver_endpoint_with_tags(client, module, endpoint)

    comparable_fields = (
        "direction",
        "ip_addresses",
        "protocols",
        "resolver_endpoint_type",
        "security_group_ids",
    )
    current = comparable_endpoint(endpoint)
    created = current is None
    desired_comparable = comparable_endpoint({field: desired[field] for field in comparable_fields})
    desired.update(desired_comparable)
    changed = not comparable_endpoints_match(current, desired_comparable)
    resource_changed = changed
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((endpoint or {}).get("Tags", [])),
            tags,
            purge_tags=purge_tags,
        )
    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if (
        changed
        and not module.check_mode
        and endpoint is not None
        and endpoint.get("Status")
        and endpoint.get("Status") != "OPERATIONAL"
    ):
        wait_for_resolver_endpoint_status(client, module, endpoint.get("Id"), {"operational"})
        return ensure_present(client, module)

    if changed and module.check_mode:
        projected_desired = desired
        if current is not None and comparable_ip_addresses_match(
            current["ip_addresses"], desired_comparable["ip_addresses"]
        ):
            projected_desired = dict(desired)
            projected_desired.pop("ip_addresses")
        endpoint = dict(endpoint or {})
        endpoint.update(snake_dict_to_camel_dict(projected_desired, capitalize_first=True))
        if tags is not None:
            endpoint = apply_tag_deltas(endpoint, tags_to_set, tag_keys_to_unset)
    elif current is None:
        endpoint = create_resolver_endpoint(client, module, desired)
        if module.params["wait"]:
            endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint)
            endpoint = resolver_endpoint_with_tags(client, module, endpoint)
    elif changed:
        if resource_changed:
            if (
                current["protocols"] != desired_comparable["protocols"]
                or current["resolver_endpoint_type"] != desired_comparable["resolver_endpoint_type"]
            ):
                update_params = {
                    "protocols": desired["protocols"],
                    "resolver_endpoint_id": endpoint.get("Id"),
                    "resolver_endpoint_type": desired["resolver_endpoint_type"],
                }

                try:
                    response = client.update_resolver_endpoint(
                        **snake_dict_to_camel_dict(update_params, capitalize_first=True),
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=("Unable to update AWS Route53 Resolver endpoint " f"{module.params['name']}"),
                    )

                endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
                if not isinstance(endpoint, dict) or not endpoint.get("Id"):
                    endpoint = get_resolver_endpoint(client, module, update_params["resolver_endpoint_id"])
                if endpoint is None:
                    module.fail_json(
                        msg=("AWS Route53 Resolver did not return the updated endpoint " f"{module.params['name']}")
                    )
                endpoint = validate_resolver_endpoint(
                    module,
                    endpoint,
                    "update_resolver_endpoint",
                    expected_id=update_params["resolver_endpoint_id"],
                )

                ip_addresses_changed = current["ip_addresses"] != desired_comparable["ip_addresses"]
                if endpoint is not None and (module.params["wait"] or ip_addresses_changed):
                    endpoint = wait_for_resolver_endpoint_status(
                        client,
                        module,
                        endpoint.get("Id"),
                        {"operational"},
                    )

                if endpoint is not None:
                    endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint)
                    endpoint = reconcile_resolver_endpoint_ip_addresses(
                        client,
                        module,
                        endpoint,
                        desired,
                    )
            else:
                endpoint = reconcile_resolver_endpoint_ip_addresses(
                    client,
                    module,
                    endpoint,
                    desired,
                )
            current = comparable_endpoint(endpoint)

            if not comparable_endpoints_match(current, desired_comparable):
                if endpoint is not None:
                    delete_resolver_endpoint(client, module, endpoint, always=True)
                endpoint = create_resolver_endpoint(client, module, desired)
                created = True
                if module.params["wait"]:
                    endpoint = resolver_endpoint_with_ip_addresses(client, module, endpoint)
        if endpoint is not None and tags is not None:
            if resource_changed and not created:
                endpoint = resolver_endpoint_with_tags(client, module, endpoint)
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(endpoint.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )
            resource_arn = endpoint.get("Arn")

            if tags_to_set or tag_keys_to_unset:
                if not isinstance(resource_arn, str) or not resource_arn:
                    module.fail_json(
                        msg=(
                            "Unable to reconcile tags for AWS Route53 Resolver endpoint "
                            f"{module.params['name']}: AWS returned an invalid endpoint ARN"
                        )
                    )
                reconcile_arn_tags(
                    module,
                    client,
                    resource_arn,
                    tags_to_set,
                    tag_keys_to_unset,
                    "AWS Route53 Resolver endpoint",
                )

            endpoint = apply_tag_deltas(endpoint, tags_to_set, tag_keys_to_unset)

    result_endpoint = boto3_resource_to_ansible_dict(endpoint, transform_tags=True, force_tags=False)
    result = {
        "changed": changed,
        "name": desired["name"],
        "resolver_endpoint": result_endpoint,
        "state": "present",
    }
    resolver_endpoint_id = result_endpoint.get("id")

    if resolver_endpoint_id is not None:
        result["resolver_endpoint_id"] = resolver_endpoint_id

    module.exit_json(**result)


def reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired):
    resolver_endpoint_id = endpoint.get("Id")
    current_ip_addresses = endpoint.get("IpAddresses") or []
    desired_ip_addresses = desired["ip_addresses"]

    remaining = list(current_ip_addresses)
    ip_addresses_to_add = []
    for ip_address in desired_ip_addresses:
        desired_comparable = comparable_ip_address(ip_address)
        match = next(
            (
                index
                for index, current_ip_address in enumerate(remaining)
                if ip_address_matches(comparable_ip_address(current_ip_address), desired_comparable)
            ),
            None,
        )
        if match is None:
            ip_addresses_to_add.append(ip_address)
        else:
            remaining.pop(match)

    ip_addresses_to_remove = remaining

    changes = []
    address_count = len(current_ip_addresses)
    while ip_addresses_to_add or ip_addresses_to_remove:
        if ip_addresses_to_add and (address_count < 20 or not ip_addresses_to_remove):
            changes.append(("add", ip_addresses_to_add.pop(0)))
            address_count += 1
        else:
            changes.append(("remove", ip_addresses_to_remove.pop(0)))
            address_count -= 1

    for index, (operation, ip_address) in enumerate(changes):
        if operation == "remove":
            normalized_ip_address = boto3_resource_to_ansible_dict(ip_address, transform_tags=False, force_tags=False)
            ip_address = {
                field: normalized_ip_address.get(field)
                for field in IP_ADDRESS_REQUEST_FIELDS
                if normalized_ip_address.get(field) is not None
            }

        try:
            request_ip_address = snake_dict_to_camel_dict(ip_address, capitalize_first=True)
            if operation == "add":
                client.associate_resolver_endpoint_ip_address(
                    IpAddress=request_ip_address,
                    ResolverEndpointId=resolver_endpoint_id,
                    aws_retry=True,
                )
            else:
                client.disassociate_resolver_endpoint_ip_address(
                    IpAddress=request_ip_address,
                    ResolverEndpointId=resolver_endpoint_id,
                    aws_retry=True,
                )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to reconcile AWS Route53 Resolver endpoint IP addresses " f"for {desired['name']}"),
            )

        if module.params["wait"] or index < len(changes) - 1:
            wait_for_resolver_endpoint_status(
                client,
                module,
                resolver_endpoint_id,
                {"operational"},
            )

    if changes and not module.params["wait"]:
        endpoint = dict(endpoint)
        endpoint["IpAddresses"] = [
            snake_dict_to_camel_dict(ip_address, capitalize_first=True) for ip_address in desired_ip_addresses
        ]
        return endpoint

    return resolver_endpoint_with_ip_addresses(
        client,
        module,
        get_resolver_endpoint(client, module, resolver_endpoint_id),
    )


def wait_for_resolver_endpoint_status(client, module, resolver_endpoint_id, statuses):
    deleted = "deleted" in statuses

    run_waiter(
        module,
        client,
        ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA,
        "resolver_endpoint_deleted" if deleted else "resolver_endpoint_operational",
        ("Timed out waiting for AWS Route53 Resolver endpoint " f"{module.params['name']}"),
        ResolverEndpointId=resolver_endpoint_id,
    )

    if deleted:
        return None
    return get_resolver_endpoint(client, module, resolver_endpoint_id)


def comparable_endpoint(endpoint):
    if not endpoint:
        return None
    normalized = boto3_resource_to_ansible_dict(endpoint, transform_tags=False, force_tags=False)
    return {
        "direction": normalized.get("direction"),
        "ip_addresses": comparable_ip_addresses(normalized.get("ip_addresses")),
        "protocols": sorted(set(normalized.get("protocols") or [])),
        "resolver_endpoint_type": normalized.get("resolver_endpoint_type"),
        "security_group_ids": sorted(set(normalized.get("security_group_ids") or [])),
    }


def comparable_ip_address(ip_address):
    normalized = boto3_resource_to_ansible_dict(ip_address, transform_tags=False, force_tags=False)
    return {field: normalized.get(field) for field in IP_ADDRESS_COMPARISON_FIELDS if normalized.get(field) is not None}


def comparable_ip_addresses(ip_addresses):
    return sorted(
        [comparable_ip_address(ip_address) for ip_address in ip_addresses or []],
        key=lambda item: json.dumps(item, sort_keys=True),
    )


def ip_address_matches(current, desired):
    return all(current.get(field) == value for field, value in desired.items())


def comparable_endpoints_match(current, desired):
    if current is None:
        return False
    if any(
        current[field] != desired[field]
        for field in (
            "direction",
            "protocols",
            "resolver_endpoint_type",
            "security_group_ids",
        )
    ):
        return False

    return comparable_ip_addresses_match(current["ip_addresses"], desired["ip_addresses"])


def comparable_ip_addresses_match(current, desired):
    remaining = list(current)
    for desired_ip_address in desired:
        match = next(
            (
                index
                for index, current_ip_address in enumerate(remaining)
                if ip_address_matches(current_ip_address, desired_ip_address)
            ),
            None,
        )
        if match is None:
            return False
        remaining.pop(match)
    return not remaining


def get_resolver_endpoint(client, module, resolver_endpoint_id):
    try:
        response = client.get_resolver_endpoint(
            ResolverEndpointId=resolver_endpoint_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver endpoint {resolver_endpoint_id}",
        )

    endpoint = response.get("ResolverEndpoint") if isinstance(response, dict) else None
    endpoint = validate_resolver_endpoint(
        module,
        endpoint,
        "get_resolver_endpoint",
        expected_id=resolver_endpoint_id,
    )
    return resolver_endpoint_with_tags(client, module, endpoint)


def get_resolver_endpoint_by_name(client, module):
    name = module.params["name"]

    endpoints = query_list(
        module,
        client,
        "list_resolver_endpoints",
        "ResolverEndpoints",
        "Unable to list AWS Route53 Resolver endpoints",
        Filters=ansible_dict_to_boto3_filter_list({"Name": name}),
    )

    endpoints = [
        validate_resolver_endpoint(module, endpoint, "list_resolver_endpoints", expected_name=name)
        for endpoint in endpoints
    ]

    if len(endpoints) > 1:
        endpoint_ids = sorted(endpoint["Id"] for endpoint in endpoints)
        module.fail_json(
            msg=(f"Multiple AWS Route53 Resolver endpoints are named {name}: " f"{', '.join(endpoint_ids)}")
        )

    return endpoints[0] if endpoints else None


def resolver_endpoint_with_ip_addresses(client, module, endpoint):
    if not endpoint:
        return endpoint
    endpoint = dict(endpoint)

    ip_addresses = query_list(
        module,
        client,
        "list_resolver_endpoint_ip_addresses",
        "IpAddresses",
        f"Unable to list AWS Route53 Resolver endpoint IP addresses for {endpoint['Id']}",
        ResolverEndpointId=endpoint["Id"],
    )
    endpoint["IpAddresses"] = validate_ip_addresses(module, ip_addresses)

    return endpoint


def resolver_endpoint_with_tags(client, module, endpoint):
    if not endpoint or not endpoint.get("Arn"):
        return endpoint
    endpoint = dict(endpoint)

    tags = query_list(
        module,
        client,
        "list_tags_for_resource",
        "Tags",
        f"Unable to list tags for AWS Route53 Resolver endpoint {endpoint['Arn']}",
        ResourceArn=endpoint["Arn"],
    )
    endpoint["Tags"] = validate_tags(module, tags)

    return endpoint


def validate_resolver_endpoint(module, endpoint, operation, expected_id=None, expected_name=None):
    if not isinstance(endpoint, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid resolver endpoint")

    endpoint_id = endpoint.get("Id")
    if not isinstance(endpoint_id, str) or not endpoint_id:
        module.fail_json(msg=f"{operation}: AWS returned a resolver endpoint without a valid ID")
    if expected_id is not None and endpoint_id != expected_id:
        module.fail_json(msg=f"{operation}: AWS returned an unexpected resolver endpoint ID {endpoint_id}")
    if expected_name is not None and endpoint.get("Name") != expected_name:
        module.fail_json(msg=f"{operation}: AWS returned an unexpected resolver endpoint name")

    for field in ("Arn", "Name", "Status"):
        if field in endpoint and not isinstance(endpoint[field], str):
            module.fail_json(msg=f"{operation}: AWS returned an invalid resolver endpoint {field}")

    return endpoint


def validate_ip_addresses(module, ip_addresses):
    for ip_address in ip_addresses:
        if not isinstance(ip_address, dict):
            module.fail_json(msg="list_resolver_endpoint_ip_addresses: AWS returned an invalid IP address")
        if not isinstance(ip_address.get("SubnetId"), str) or not ip_address["SubnetId"]:
            module.fail_json(msg="list_resolver_endpoint_ip_addresses: AWS returned an IP address without a subnet ID")
        for field in ("Ip", "IpId", "Ipv6"):
            if field in ip_address and not isinstance(ip_address[field], str):
                module.fail_json(msg=f"list_resolver_endpoint_ip_addresses: AWS returned an invalid {field}")
    return ip_addresses


def validate_tags(module, tags):
    for tag in tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str):
            module.fail_json(msg="list_tags_for_resource: AWS returned an invalid tag")
    return tags


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "direction": {
                "choices": ["inbound", "outbound"],
                "type": "str",
            },
            "ip_addresses": {
                "elements": "dict",
                "mutually_exclusive": [["ip", "ipv6"]],
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
            "purge_tags": {"default": True, "type": "bool"},
            "resolver_endpoint_type": {
                "choices": ["dualstack", "ipv4", "ipv6"],
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
            "tags": {"type": "dict"},
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 5, "type": "int"},
            "wait_timeout": {"default": 300, "type": "int"},
        },
        required_if=[
            ("state", "present", ["direction", "ip_addresses", "security_group_ids"]),
        ],
        supports_check_mode=True,
    )
    state = module.params["state"]
    tags = module.params["tags"]

    name = module.params["name"]
    if len(name) > 64 or name.isdigit() or re.fullmatch(r"[a-zA-Z0-9\-_ ']+", name) is None:
        module.fail_json(msg="name must be a valid resolver endpoint name of at most 64 characters")

    if state == "present":
        if not 2 <= len(module.params["ip_addresses"] or []) <= 20:
            module.fail_json(msg="ip_addresses must contain 2 to 20 entries")
        comparable_ip_address_values = comparable_ip_addresses(module.params["ip_addresses"])
        if len({json.dumps(item, sort_keys=True) for item in comparable_ip_address_values}) != len(
            comparable_ip_address_values
        ):
            module.fail_json(msg="ip_addresses entries must be unique")
        if not 1 <= len(set(module.params["protocols"])) <= 2:
            module.fail_json(msg="protocols must contain 1 or 2 entries")
        if not module.params["security_group_ids"]:
            module.fail_json(msg="security_group_ids must contain at least one entry")
        if any(not 1 <= len(group_id) <= 64 for group_id in module.params["security_group_ids"]):
            module.fail_json(msg="security_group_ids entries must contain 1 to 64 characters")
        for entry in module.params["ip_addresses"]:
            if not 1 <= len(entry["subnet_id"]) <= 32:
                module.fail_json(msg="ip_addresses[].subnet_id must contain 1 to 32 characters")
            for field, version in (("ip", 4), ("ipv6", 6)):
                value = entry.get(field)
                if value is None:
                    continue
                try:
                    valid = ipaddress.ip_address(value).version == version
                except ValueError:
                    valid = False
                if not valid:
                    module.fail_json(msg=f"ip_addresses[].{field} must be a valid IPv{version} address")
        require_valid_tags(module, tags, 200)

    require_positive_wait_bounds(module, always=state == "present")

    client = module.client("route53resolver", retry_decorator=AWSRetry.jittered_backoff())
    method_names = {"list_resolver_endpoints"}
    if state == "present":
        method_names.update(
            {
                "associate_resolver_endpoint_ip_address",
                "create_resolver_endpoint",
                "delete_resolver_endpoint",
                "disassociate_resolver_endpoint_ip_address",
                "get_resolver_endpoint",
                "list_resolver_endpoint_ip_addresses",
                "list_tags_for_resource",
                "update_resolver_endpoint",
            }
        )
        if tags:
            method_names.add("tag_resource")
        if tags is not None and module.params["purge_tags"]:
            method_names.add("untag_resource")

    if state == "absent":
        method_names.add("delete_resolver_endpoint")
        if module.params["wait"]:
            method_names.add("get_resolver_endpoint")

    required_method_parameters = {
        "associate_resolver_endpoint_ip_address": {
            "IpAddress",
            "ResolverEndpointId",
        },
        "create_resolver_endpoint": {
            "CreatorRequestId",
            "Direction",
            "IpAddresses",
            "Name",
            "Protocols",
            "ResolverEndpointType",
            "SecurityGroupIds",
            "Tags",
        },
        "delete_resolver_endpoint": {"ResolverEndpointId"},
        "disassociate_resolver_endpoint_ip_address": {
            "IpAddress",
            "ResolverEndpointId",
        },
        "get_resolver_endpoint": {"ResolverEndpointId"},
        "list_resolver_endpoint_ip_addresses": {
            "MaxResults",
            "NextToken",
            "ResolverEndpointId",
        },
        "list_resolver_endpoints": {"Filters", "MaxResults", "NextToken"},
        "list_tags_for_resource": {"MaxResults", "NextToken", "ResourceArn"},
        "tag_resource": {"ResourceArn", "Tags"},
        "untag_resource": {"ResourceArn", "TagKeys"},
        "update_resolver_endpoint": {
            "Protocols",
            "ResolverEndpointId",
            "ResolverEndpointType",
        },
    }
    if tags is None:
        required_method_parameters["create_resolver_endpoint"].discard("Tags")
    require_client_methods(
        module,
        client,
        "Route53 Resolver",
        {name: required_method_parameters.get(name, ()) for name in method_names},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
