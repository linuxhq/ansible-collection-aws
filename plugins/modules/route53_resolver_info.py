#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_info
version_added: '1.9.0'
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
      - Boolean and numeric values, including list entries, are converted to strings.
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
  contains:
    arn:
      description: The endpoint ARN.
      returned: always
      type: str
    creation_time:
      description: The time the endpoint was created.
      returned: when returned by AWS
      type: str
    direction:
      description: The endpoint direction.
      returned: always
      type: str
      sample: OUTBOUND
    host_vpc_id:
      description: The VPC the endpoint is in.
      returned: always
      type: str
    id:
      description: The endpoint ID.
      returned: always
      type: str
    ip_address_count:
      description: The number of IP addresses.
      returned: always
      type: int
    ip_addresses:
      description: The endpoint IP addresses.
      returned: always
      type: list
      elements: dict
      contains:
        ip:
          description: The IPv4 address.
          returned: when assigned
          type: str
        ip_id:
          description: The IP address ID.
          returned: always
          type: str
        ipv6:
          description: The IPv6 address.
          returned: when assigned
          type: str
        status:
          description: The IP address status.
          returned: when returned by AWS
          type: str
        subnet_id:
          description: The subnet ID.
          returned: always
          type: str
    name:
      description: The endpoint name.
      returned: always
      type: str
    protocols:
      description: The endpoint protocols.
      returned: always
      type: list
      elements: str
    resolver_endpoint_type:
      description: The endpoint type.
      returned: always
      type: str
      sample: IPV4
    security_group_ids:
      description: The endpoint security group IDs.
      returned: always
      type: list
      elements: str
    status:
      description: The endpoint status.
      returned: always
      type: str
      sample: OPERATIONAL
    status_message:
      description: Details about the endpoint status.
      returned: when returned by AWS
      type: str
    tags:
      description: The endpoint tags with key case preserved.
      returned: always
      type: dict
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
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.filters import (
    ansible_dict_to_string_filter_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    response_items,
    validate_ip_addresses,
    validate_tags,
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
        {"list_resolver_endpoints": ("Filters", "MaxResults", "NextToken")},
    )

    filters = module.params["filters"]
    request = {}
    if filters:
        request["Filters"] = ansible_dict_to_string_filter_list(filters)

    resolver_endpoints = query_list(
        module,
        client,
        "list_resolver_endpoints",
        "ResolverEndpoints",
        "Unable to list AWS Route53 Resolver endpoints",
        **request,
    )

    if resolver_endpoints:
        require_client_methods(
            module,
            client,
            "Route53 Resolver",
            {
                "list_resolver_endpoint_ip_addresses": ("MaxResults", "NextToken", "ResolverEndpointId"),
                "list_tags_for_resource": ("MaxResults", "NextToken", "ResourceArn"),
            },
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
                msg=f"Unable to list AWS Route53 Resolver endpoint IP addresses for {endpoint_id}",
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
                    msg=f"Unable to list tags for AWS Route53 Resolver endpoint {endpoint_arn}",
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


def validate_endpoint(module, endpoint):
    if not isinstance(endpoint, dict):
        module.fail_json(msg="list_resolver_endpoints: AWS returned an invalid resolver endpoint")

    endpoint_id = endpoint.get("Id")
    if not isinstance(endpoint_id, str) or not endpoint_id:
        module.fail_json(msg="list_resolver_endpoints: AWS returned a resolver endpoint without a valid ID")

    if "Arn" in endpoint and not isinstance(endpoint["Arn"], str):
        module.fail_json(msg="list_resolver_endpoints: AWS returned an invalid resolver endpoint ARN")

    return endpoint


if __name__ == "__main__":
    main()
