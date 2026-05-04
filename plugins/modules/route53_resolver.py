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
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.route53 import (
    list_resolver_endpoints,
    normalize_resolver_endpoint_with_ip_addresses,
)


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


def get_resolver_endpoint(client, module, resolver_endpoint_id):
    get_resolver_endpoint = AWSRetry.jittered_backoff()(client.get_resolver_endpoint)
    try:
        response = get_resolver_endpoint(ResolverEndpointId=resolver_endpoint_id)
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver endpoint {resolver_endpoint_id}",
        )
    return response.get("ResolverEndpoint")


def get_resolver_endpoint_by_name(client, module, name):
    for endpoint in list_resolver_endpoints(client, module):
        if endpoint.get("Name") == name:
            return endpoint
    return None


def wait_for_resolver_endpoint_status(
    client, module, resolver_endpoint_id, statuses, name
):
    deadline = time.time() + module.params["wait_timeout"]

    while time.time() < deadline:
        endpoint = get_resolver_endpoint(client, module, resolver_endpoint_id)
        if endpoint is None and "deleted" in statuses:
            return None
        if endpoint is not None and endpoint.get("Status", "").lower() in statuses:
            return endpoint
        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=f"Timed out waiting for AWS Route53 Resolver endpoint {name}",
        resolver_endpoint_id=resolver_endpoint_id,
    )


def ensure_present(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module, module.params["name"])
    changed = endpoint is None

    if changed and not module.check_mode:
        create_resolver_endpoint = AWSRetry.jittered_backoff()(
            client.create_resolver_endpoint
        )
        try:
            response = create_resolver_endpoint(
                CreatorRequestId=module.params["name"],
                Direction=module.params["direction"].upper(),
                IpAddresses=aws_ip_addresses(module.params["ip_addresses"]),
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
            endpoint = wait_for_resolver_endpoint_status(
                client, module, endpoint["Id"], {"operational"}, module.params["name"]
            )
    elif changed and module.check_mode:
        endpoint = {"Name": module.params["name"]}

    result = {
        "changed": changed,
        "name": module.params["name"],
        "resolver_endpoint": normalize_resolver_endpoint_with_ip_addresses(
            client, module, endpoint
        ),
        "state": "present",
    }
    if endpoint is not None and endpoint.get("Id") is not None:
        result["resolver_endpoint_id"] = endpoint["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    endpoint = get_resolver_endpoint_by_name(client, module, module.params["name"])
    changed = endpoint is not None

    if changed and not module.check_mode:
        resolver_endpoint_id = endpoint["Id"]
        delete_resolver_endpoint = AWSRetry.jittered_backoff()(
            client.delete_resolver_endpoint
        )
        try:
            delete_resolver_endpoint(ResolverEndpointId=resolver_endpoint_id)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 Resolver endpoint {module.params['name']}",
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
