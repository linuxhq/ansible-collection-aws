#!/usr/bin/python
# -*- coding: utf-8 -*-
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
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
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

    method_names = {
        "list_resolver_endpoint_ip_addresses",
        "list_resolver_endpoints",
        "list_tags_for_resource",
    }
    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=(
                    "Installed botocore does not support Route53 Resolver "
                    f"{method_name}"
                )
            )

    required_method_parameters = {
        "list_resolver_endpoint_ip_addresses": {
            "MaxResults",
            "NextToken",
            "ResolverEndpointId",
        },
        "list_resolver_endpoints": {"Filters", "MaxResults", "NextToken"},
        "list_tags_for_resource": {"MaxResults", "NextToken", "ResourceArn"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Route53 Resolver "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    request = {}
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])

    try:
        resolver_endpoints = paginated_query_with_retries(
            client, "list_resolver_endpoints", **request
        ).get("ResolverEndpoints", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Route53 Resolver endpoints")

    normalized_endpoints = []
    for endpoint in resolver_endpoints:
        try:
            ip_addresses = paginated_query_with_retries(
                client,
                "list_resolver_endpoint_ip_addresses",
                ResolverEndpointId=endpoint["Id"],
            ).get("IpAddresses", [])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to list AWS Route53 Resolver endpoint IP addresses "
                    f"for {endpoint['Id']}"
                ),
            )

        tags = []
        if endpoint.get("Arn"):
            try:
                tags = paginated_query_with_retries(
                    client,
                    "list_tags_for_resource",
                    ResourceArn=endpoint["Arn"],
                ).get("Tags", [])
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to list tags for AWS Route53 Resolver endpoint "
                        f"{endpoint['Arn']}"
                    ),
                )

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


if __name__ == "__main__":
    main()
