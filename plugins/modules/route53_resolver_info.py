#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_info
version_added: "1.9.5"
short_description: Gather information about AWS Route53 Resolver endpoints
description:
  - Gathers information about AWS Route53 Resolver endpoints.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when listing Route53 Resolver endpoints.
      - Filter names and values are passed to the Route53 Resolver C(ListResolverEndpoints) API.
    type: dict
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
    filters:
      Name: molecule
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
    ansible_dict_to_boto3_filter_list,
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
            "filters": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )
    request = {}
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])
    resolver_endpoints = paginated_query_with_retries(
        client, "list_resolver_endpoints", **request
    ).get("ResolverEndpoints", [])

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
