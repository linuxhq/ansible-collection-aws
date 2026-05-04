#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_info
version_added: 1.9.1
short_description: Gather information about AWS Route53 Resolver endpoints
description:
  - Gathers information about AWS Route53 Resolver endpoints.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The Route53 Resolver endpoint name to query.
      - When omitted, all resolver endpoints are returned.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about Route53 Resolver endpoints
  linuxhq.aws.route53_resolver_info:

- name: Gather information about a single Route53 Resolver endpoint
  linuxhq.aws.route53_resolver_info:
    name: molecule
"""

RETURN = r"""
resolver_endpoints:
  description:
    - The Route53 Resolver endpoints.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


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


def normalize(endpoint):
    normalized = camel_dict_to_snake_dict(endpoint)
    if "ip_addresses" in normalized:
        normalized["ip_addresses"] = endpoint.get("IpAddresses", [])
    return normalized


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53resolver")
    resolver_endpoints = list_resolver_endpoints(client, module)

    if module.params["name"] is not None:
        resolver_endpoints = [
            endpoint
            for endpoint in resolver_endpoints
            if endpoint.get("Name") == module.params["name"]
        ]

    module.exit_json(
        changed=False,
        resolver_endpoints=[normalize(endpoint) for endpoint in resolver_endpoints],
    )


if __name__ == "__main__":
    main()
