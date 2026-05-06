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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    get_resolver_endpoint_by_name,
    list_resolver_endpoints,
    resolver_endpoint_with_ip_addresses,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53resolver")
    if module.params["name"] is None:
        resolver_endpoints = list_resolver_endpoints(client, module)
    else:
        resolver_endpoint = get_resolver_endpoint_by_name(
            client,
            module,
            module.params["name"],
        )
        resolver_endpoints = (
            [resolver_endpoint] if resolver_endpoint is not None else []
        )

    module.exit_json(
        changed=False,
        resolver_endpoints=[
            aws_resource_to_snake_dict(
                resolver_endpoint_with_ip_addresses(client, module, endpoint)
            )
            for endpoint in resolver_endpoints
        ],
    )


if __name__ == "__main__":
    main()
