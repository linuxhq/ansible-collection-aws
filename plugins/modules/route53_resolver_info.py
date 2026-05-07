#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_info
version_added: "1.9.0"
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def resource_tags(client, module, resource):
    if not resource.get("Arn"):
        return []
    try:
        return client.list_tags_for_resource(
            ResourceArn=resource["Arn"],
            aws_retry=True,
        ).get("Tags", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Route53 Resolver endpoint {resource['Arn']}",
        )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )
    resolver_endpoints = paginated_query_with_retries(
        client, "list_resolver_endpoints"
    ).get("ResolverEndpoints", [])
    if module.params["name"] is not None:
        resolver_endpoints = [
            endpoint
            for endpoint in resolver_endpoints
            if endpoint.get("Name") == module.params["name"]
        ]

    module.exit_json(
        changed=False,
        resolver_endpoints=[
            boto3_resource_to_ansible_dict(
                dict(
                    endpoint,
                    IpAddresses=paginated_query_with_retries(
                        client,
                        "list_resolver_endpoint_ip_addresses",
                        ResolverEndpointId=endpoint["Id"],
                    ).get("IpAddresses", []),
                    Tags=resource_tags(client, module, endpoint),
                ),
                transform_tags=True,
                force_tags=False,
            )
            for endpoint in resolver_endpoints
        ],
    )


if __name__ == "__main__":
    main()
