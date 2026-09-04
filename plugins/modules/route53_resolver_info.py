#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_info
short_description: Gather information about aws route53 resolver endpoints
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
attributes:
  check_mode:
    description: This module does not modify AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - Each endpoint includes C(ip_addresses) and C(tags) gathered by the
      module.
  returned: always
  type: list
  elements: dict
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53resolver", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "Route53 Resolver",
        {
            "list_resolver_endpoint_ip_addresses": (
                "MaxResults",
                "NextToken",
                "ResolverEndpointId",
            ),
            "list_resolver_endpoints": ("Filters", "MaxResults", "NextToken"),
            "list_tags_for_resource": ("MaxResults", "NextToken", "ResourceArn"),
        },
    )

    filters = module.params["filters"]
    request = {}
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    resolver_endpoints = query_list(
        module,
        client,
        "list_resolver_endpoints",
        "ResolverEndpoints",
        "Unable to list AWS Route53 Resolver endpoints",
        **request,
    )

    normalized_endpoints = []
    for endpoint in resolver_endpoints:
        endpoint = validate_endpoint(module, endpoint)
        endpoint_id = endpoint["Id"]
        try:
            response = paginated_query_with_retries(
                client,
                "list_resolver_endpoint_ip_addresses",
                ResolverEndpointId=endpoint_id,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to list AWS Route53 Resolver endpoint IP addresses " f"for {endpoint_id}"),
            )
        ip_addresses = validate_ip_addresses(
            module,
            response_items(module, response, "IpAddresses", "list_resolver_endpoint_ip_addresses"),
        )

        tags = []
        endpoint_arn = endpoint.get("Arn")
        if endpoint_arn:
            try:
                response = paginated_query_with_retries(
                    client,
                    "list_tags_for_resource",
                    ResourceArn=endpoint_arn,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                continue
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=("Unable to list tags for AWS Route53 Resolver endpoint " f"{endpoint_arn}"),
                )
            tags = validate_tags(module, response_items(module, response, "Tags", "list_tags_for_resource"))

        normalized_endpoints.append(
            boto3_resource_to_ansible_dict(
                dict(endpoint, IpAddresses=ip_addresses, Tags=tags),
                transform_tags=True,
                force_tags=False,
            )
        )

    module.exit_json(
        changed=False,
        resolver_endpoints=normalized_endpoints,
    )


def response_items(module, response, key, operation):
    if not isinstance(response, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid response")
    items = response.get(key, [])
    if not isinstance(items, list):
        module.fail_json(msg=f"{operation}: AWS returned an invalid {key} value")
    return items


def validate_endpoint(module, endpoint):
    if not isinstance(endpoint, dict):
        module.fail_json(msg="list_resolver_endpoints: AWS returned an invalid resolver endpoint")
    endpoint_id = endpoint.get("Id")
    if not isinstance(endpoint_id, str) or not endpoint_id:
        module.fail_json(msg="list_resolver_endpoints: AWS returned a resolver endpoint without a valid ID")
    if "Arn" in endpoint and not isinstance(endpoint["Arn"], str):
        module.fail_json(msg="list_resolver_endpoints: AWS returned an invalid resolver endpoint ARN")
    return endpoint


def validate_ip_addresses(module, ip_addresses):
    for ip_address in ip_addresses:
        if not isinstance(ip_address, dict):
            module.fail_json(msg="list_resolver_endpoint_ip_addresses: AWS returned an invalid IP address")
        if not isinstance(ip_address.get("SubnetId"), str) or not ip_address["SubnetId"]:
            module.fail_json(msg="list_resolver_endpoint_ip_addresses: AWS returned an IP address without a subnet ID")
    return ip_addresses


def validate_tags(module, tags):
    for tag in tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str):
            module.fail_json(msg="list_tags_for_resource: AWS returned an invalid tag")
    return tags


if __name__ == "__main__":
    main()
