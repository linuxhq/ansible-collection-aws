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
      - The resolver endpoint IP address definitions in AWS format.
      - This is required when O(state=present).
    elements: dict
    type: list
  name:
    description:
      - The resolver endpoint name.
    required: true
    type: str
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
      - SubnetId: subnet-0123456789abcdef0
        Ip: 192.168.0.125
      - SubnetId: subnet-0123456789abcdef1
        Ip: 192.168.0.253
    name: molecule
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

import time

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in (
        "ResourceNotFoundException",
    )


def list_resolver_endpoints(client, module):
    endpoints = []
    next_token = None

    while True:
        kwargs = {}
        if next_token:
            kwargs["NextToken"] = next_token

        try:
            response = client.list_resolver_endpoints(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Route53 Resolver endpoints",
            )

        endpoints.extend(response.get("ResolverEndpoints", []))
        next_token = response.get("NextToken")
        if not next_token:
            break

    return endpoints


def get_resolver_endpoint_by_name(client, module):
    for endpoint in list_resolver_endpoints(client, module):
        if endpoint.get("Name") == module.params["name"]:
            return endpoint
    return None


def get_resolver_endpoint(client, module, resolver_endpoint_id):
    try:
        response = client.get_resolver_endpoint(ResolverEndpointId=resolver_endpoint_id)
    except Exception as e:
        if is_not_found_error(e):
            return None
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver endpoint {resolver_endpoint_id}",
        )
    return response.get("ResolverEndpoint")


def wait_for_status(client, module, resolver_endpoint_id, statuses):
    deadline = time.time() + module.params["wait_timeout"]

    while time.time() < deadline:
        endpoint = get_resolver_endpoint(client, module, resolver_endpoint_id)
        if endpoint is None and "deleted" in statuses:
            return None
        if endpoint is not None and endpoint.get("Status", "").lower() in statuses:
            return endpoint
        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=f"Timed out waiting for AWS Route53 Resolver endpoint {module.params['name']}",
        resolver_endpoint_id=resolver_endpoint_id,
    )


def normalize(endpoint):
    if endpoint is None:
        return None
    return camel_dict_to_snake_dict(endpoint)


def ensure_present(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module)
    changed = endpoint is None

    if changed and not module.check_mode:
        try:
            response = client.create_resolver_endpoint(
                CreatorRequestId=module.params["name"],
                Direction=module.params["direction"].upper(),
                IpAddresses=module.params["ip_addresses"],
                Name=module.params["name"],
                ResolverEndpointType=module.params["resolver_endpoint_type"].upper(),
                SecurityGroupIds=module.params["security_group_ids"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 Resolver endpoint {module.params['name']}",
            )
        endpoint = response.get("ResolverEndpoint")
        if module.params["wait"]:
            endpoint = wait_for_status(client, module, endpoint["Id"], {"operational"})
    elif changed and module.check_mode:
        endpoint = {"Name": module.params["name"]}

    result = {
        "changed": changed,
        "name": module.params["name"],
        "resolver_endpoint": normalize(endpoint),
        "state": "present",
    }
    if endpoint is not None and endpoint.get("Id") is not None:
        result["resolver_endpoint_id"] = endpoint["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module)
    changed = endpoint is not None

    if changed and not module.check_mode:
        resolver_endpoint_id = endpoint["Id"]
        try:
            client.delete_resolver_endpoint(ResolverEndpointId=resolver_endpoint_id)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 Resolver endpoint {module.params['name']}",
            )
        if module.params["wait"]:
            wait_for_status(client, module, resolver_endpoint_id, {"deleted"})

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
                "type": "list",
            },
            "name": {"required": True, "type": "str"},
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
