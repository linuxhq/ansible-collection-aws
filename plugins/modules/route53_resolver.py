#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver
version_added: "1.9.5"
short_description: Manage AWS Route53 Resolver endpoints
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
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
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
    type: dict
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
    tags:
      Name: molecule

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

import json

from ansible.module_utils.common.dict_transformations import (
    recursive_diff,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
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
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
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


class ResolverEndpointWaiterFactory(BaseWaiterFactory):
    @property
    def _waiter_model_data(self):
        return ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA


def create_resolver_endpoint(client, module, desired):
    try:
        endpoint = client.create_resolver_endpoint(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "creator_request_id": desired["name"],
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
        ).get("ResolverEndpoint")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to create AWS Route53 Resolver endpoint {desired['name']}",
        )
    if module.params["wait"]:
        resolver_endpoint_id = endpoint.get("Id")
        endpoint = wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            {"operational"},
            desired["name"],
        )
    return endpoint


def delete_resolver_endpoint(client, module, endpoint, name):
    resolver_endpoint_id = endpoint.get("Id")
    try:
        client.delete_resolver_endpoint(
            ResolverEndpointId=resolver_endpoint_id,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to delete AWS Route53 Resolver endpoint {name}"
        )
    if module.params["wait"]:
        wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            {"deleted"},
            name,
        )


def ensure_absent(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module.params["name"])
    changed = endpoint is not None

    if changed and not module.check_mode:
        delete_resolver_endpoint(client, module, endpoint, module.params["name"])

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    desired = {
        "direction": module.params["direction"].upper(),
        "ip_addresses": module.params["ip_addresses"],
        "name": module.params["name"],
        "protocols": [
            PROTOCOLS[protocol.lower()] for protocol in module.params["protocols"] or []
        ],
        "resolver_endpoint_type": module.params["resolver_endpoint_type"].upper(),
        "security_group_ids": module.params["security_group_ids"],
    }
    endpoint = get_resolver_endpoint_by_name(client, desired["name"])
    if endpoint is not None:
        endpoint = resolver_endpoint_with_ip_addresses(client, endpoint)
        endpoint = resolver_endpoint_with_tags(client, module, endpoint)

    comparable_fields = (
        "direction",
        "ip_addresses",
        "protocols",
        "resolver_endpoint_type",
        "security_group_ids",
    )
    current = comparable_endpoint(endpoint)
    desired_comparable = comparable_endpoint(
        {field: desired[field] for field in comparable_fields}
    )
    desired.update(desired_comparable)
    if current is None:
        changed = True
    else:
        changed = (
            recursive_diff((current) or {}, (desired_comparable) or {}) is not None
        )
    resource_changed = changed
    tags_to_set, tag_keys_to_unset = tag_changes(module, endpoint)
    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if current is None and not module.check_mode:
        endpoint = resolver_endpoint_with_ip_addresses(
            client,
            create_resolver_endpoint(client, module, desired),
        )
        endpoint = resolver_endpoint_with_tags(client, module, endpoint)
    elif current is None and module.check_mode:
        endpoint = desired
        if module.params["tags"] is not None:
            endpoint["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
    elif changed and not module.check_mode:
        if resource_changed:
            endpoint = update_resolver_endpoint(
                client,
                module,
                endpoint,
                desired,
            )
            current = comparable_endpoint(endpoint)
            desired_comparable = comparable_endpoint(
                {field: desired[field] for field in comparable_fields}
            )
            if recursive_diff((current) or {}, (desired_comparable) or {}) is not None:
                delete_resolver_endpoint(client, module, endpoint, desired["name"])
                endpoint = resolver_endpoint_with_ip_addresses(
                    client,
                    create_resolver_endpoint(client, module, desired),
                )
        if endpoint is not None and module.params["tags"] is not None:
            endpoint = resolver_endpoint_with_tags(client, module, endpoint)
            tags_to_set, tag_keys_to_unset = tag_changes(module, endpoint)
            apply_tag_changes(
                client,
                module,
                endpoint.get("Arn"),
                tags_to_set,
                tag_keys_to_unset,
            )
            endpoint = resolver_endpoint_with_tags(client, module, endpoint)
    elif changed and module.check_mode:
        endpoint = desired
        if module.params["tags"] is not None:
            endpoint["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])

    result_endpoint = boto3_resource_to_ansible_dict(
        endpoint, transform_tags=True, force_tags=False
    )
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

    current_comparable = comparable_ip_addresses(current_ip_addresses)
    desired_comparable = comparable_ip_addresses(desired_ip_addresses)
    ip_addresses_to_add = [
        ip_address
        for ip_address in desired_ip_addresses
        if comparable_ip_address(ip_address) not in current_comparable
    ]
    ip_addresses_to_remove = [
        ip_address
        for ip_address in current_ip_addresses
        if comparable_ip_address(ip_address) not in desired_comparable
    ]

    for ip_address in ip_addresses_to_add:
        try:
            client.associate_resolver_endpoint_ip_address(
                IpAddress=snake_dict_to_camel_dict(ip_address, capitalize_first=True),
                ResolverEndpointId=resolver_endpoint_id,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to reconcile AWS Route53 Resolver endpoint IP addresses "
                    f"for {desired['name']}"
                ),
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
        normalized_ip_address = boto3_resource_to_ansible_dict(
            ip_address, transform_tags=False, force_tags=False
        )
        request_ip_address = {
            field: normalized_ip_address.get(field)
            for field in IP_ADDRESS_REQUEST_FIELDS
            if normalized_ip_address.get(field) is not None
        }
        try:
            client.disassociate_resolver_endpoint_ip_address(
                IpAddress=snake_dict_to_camel_dict(
                    request_ip_address, capitalize_first=True
                ),
                ResolverEndpointId=resolver_endpoint_id,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to reconcile AWS Route53 Resolver endpoint IP addresses "
                    f"for {desired['name']}"
                ),
            )
        if module.params["wait"]:
            wait_for_resolver_endpoint_status(
                client,
                module,
                resolver_endpoint_id,
                {"operational"},
                desired["name"],
            )

    return resolver_endpoint_with_ip_addresses(
        client,
        get_resolver_endpoint(client, module, resolver_endpoint_id),
    )


def update_resolver_endpoint(client, module, endpoint, desired):
    update_params = {
        "protocols": desired["protocols"],
        "resolver_endpoint_id": endpoint.get("Id"),
        "resolver_endpoint_type": desired["resolver_endpoint_type"],
    }

    endpoint = resolver_endpoint_with_ip_addresses(
        client,
        update_resolver_endpoint_call(client, module, update_params, desired["name"]),
    )
    if module.params["wait"]:
        resolver_endpoint_id = endpoint.get("Id")
        endpoint = wait_for_resolver_endpoint_status(
            client,
            module,
            resolver_endpoint_id,
            {"operational"},
            desired["name"],
        )
    endpoint = reconcile_resolver_endpoint_ip_addresses(
        client,
        module,
        endpoint,
        desired,
    )

    return endpoint


def tag_changes(module, resource):
    if module.params["tags"] is None:
        return {}, []
    current_tags = boto3_tag_list_to_ansible_dict((resource or {}).get("Tags", []))
    return compare_aws_tags(
        current_tags,
        module.params["tags"],
        purge_tags=module.params["purge_tags"],
    )


def apply_tag_changes(client, module, resource_arn, tags_to_set, tag_keys_to_unset):
    if not resource_arn:
        return
    if tag_keys_to_unset:
        try:
            client.untag_resource(
                ResourceArn=resource_arn,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from AWS Route53 Resolver endpoint {resource_arn}",
            )
    if tags_to_set:
        try:
            client.tag_resource(
                ResourceArn=resource_arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag AWS Route53 Resolver endpoint {resource_arn}",
            )


def wait_for_resolver_endpoint_status(
    client, module, resolver_endpoint_id, statuses, name
):
    deleted = "deleted" in statuses
    try:
        waiter = ResolverEndpointWaiterFactory().get_waiter(
            client,
            "resolver_endpoint_deleted" if deleted else "resolver_endpoint_operational",
        )
        waiter.wait(
            ResolverEndpointId=resolver_endpoint_id,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=max(1, module.params["wait_delay"]),
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Timed out waiting for AWS Route53 Resolver endpoint {name}"
        )
    if deleted:
        return None
    return get_resolver_endpoint(client, module, resolver_endpoint_id)


def update_resolver_endpoint_call(client, module, update_params, name):
    try:
        return client.update_resolver_endpoint(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(update_params, capitalize_first=True)
            ),
            aws_retry=True,
        ).get("ResolverEndpoint")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to update AWS Route53 Resolver endpoint {name}",
        )


def comparable_endpoint(endpoint):
    if not endpoint:
        return None
    normalized = boto3_resource_to_ansible_dict(
        endpoint, transform_tags=False, force_tags=False
    )
    return {
        "direction": normalized.get("direction"),
        "ip_addresses": comparable_ip_addresses(normalized.get("ip_addresses")),
        "protocols": sorted(normalized.get("protocols") or []),
        "resolver_endpoint_type": normalized.get("resolver_endpoint_type"),
        "security_group_ids": sorted(normalized.get("security_group_ids") or []),
    }


def comparable_ip_address(ip_address):
    normalized = boto3_resource_to_ansible_dict(
        ip_address, transform_tags=False, force_tags=False
    )
    return {
        field: normalized.get(field)
        for field in IP_ADDRESS_COMPARISON_FIELDS
        if normalized.get(field) is not None
    }


def comparable_ip_addresses(ip_addresses):
    return sorted(
        [comparable_ip_address(ip_address) for ip_address in ip_addresses or []],
        key=lambda item: json.dumps(item, sort_keys=True),
    )


def get_resolver_endpoint(client, module, resolver_endpoint_id):
    try:
        endpoint = client.get_resolver_endpoint(
            ResolverEndpointId=resolver_endpoint_id,
            aws_retry=True,
        ).get("ResolverEndpoint")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver endpoint {resolver_endpoint_id}",
        )
    return resolver_endpoint_with_tags(client, module, endpoint)


def get_resolver_endpoint_by_name(client, name):
    return next(
        (
            endpoint
            for endpoint in paginated_query_with_retries(
                client, "list_resolver_endpoints"
            ).get("ResolverEndpoints", [])
            if endpoint.get("Name") == name
        ),
        None,
    )


def resolver_endpoint_with_ip_addresses(client, endpoint):
    if not endpoint:
        return endpoint
    endpoint = dict(endpoint)
    endpoint["IpAddresses"] = paginated_query_with_retries(
        client,
        "list_resolver_endpoint_ip_addresses",
        ResolverEndpointId=endpoint["Id"],
    ).get("IpAddresses", [])
    return endpoint


def resolver_endpoint_with_tags(client, module, endpoint):
    if not endpoint or not endpoint.get("Arn"):
        return endpoint
    endpoint = dict(endpoint)
    try:
        endpoint["Tags"] = client.list_tags_for_resource(
            ResourceArn=endpoint["Arn"],
            aws_retry=True,
        ).get("Tags", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Route53 Resolver endpoint {endpoint['Arn']}",
        )
    return endpoint


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
            "purge_tags": {"default": True, "type": "bool"},
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
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
