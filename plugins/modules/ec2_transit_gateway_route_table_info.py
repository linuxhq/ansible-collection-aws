#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_transit_gateway_route_table_info
short_description: Gather information about EC2 transit gateway route tables
description:
  - Gathers information about AWS EC2 transit gateway route tables.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 transit gateway route
        tables.
      - Filter names and values are passed to the EC2
        C(DescribeTransitGatewayRouteTables) API.
    type: dict
  transit_gateway_route_table_ids:
    description:
      - EC2 transit gateway route table IDs used to limit the result set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about all transit gateway route tables
  linuxhq.aws.ec2_transit_gateway_route_table_info:

- name: Gather information about available transit gateway route tables
  linuxhq.aws.ec2_transit_gateway_route_table_info:
    filters:
      state: available

- name: Gather information about selected transit gateway route tables
  linuxhq.aws.ec2_transit_gateway_route_table_info:
    transit_gateway_route_table_ids:
      - tgw-rtb-0123456789abcdef0
"""

RETURN = r"""
transit_gateway_route_tables:
  description:
    - A list of EC2 transit gateway route tables.
    - Each route table includes a C(routes) list gathered from
      C(SearchTransitGatewayRoutes) when the route table is available.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def route_sort_key(route):
    return (
        route.get("DestinationCidrBlock") or route.get("PrefixListId") or "",
        route.get("Type") or "",
        route.get("State") or "",
    )


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "transit_gateway_route_table_ids": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "EC2",
        {
            "describe_transit_gateway_route_tables": (
                "Filters",
                "TransitGatewayRouteTableIds",
            ),
            "search_transit_gateway_routes": (
                "Filters",
                "MaxResults",
                "TransitGatewayRouteTableId",
            ),
        },
    )

    filters = module.params["filters"]
    transit_gateway_route_table_ids = module.params["transit_gateway_route_table_ids"]

    request = {}
    if transit_gateway_route_table_ids:
        request["TransitGatewayRouteTableIds"] = transit_gateway_route_table_ids
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    route_tables = query_list(
        module,
        client,
        "describe_transit_gateway_route_tables",
        "TransitGatewayRouteTables",
        "Unable to describe EC2 transit gateway route tables",
        **request,
    )

    route_tables_with_routes = []
    for route_table in route_tables:
        route_table = dict(route_table)
        route_table["Routes"] = []

        if route_table.get("State") == "available":
            transit_gateway_route_table_id = route_table["TransitGatewayRouteTableId"]

            try:
                response = client.search_transit_gateway_routes(
                    TransitGatewayRouteTableId=transit_gateway_route_table_id,
                    Filters=ansible_dict_to_boto3_filter_list(
                        {"type": ["static", "propagated"]}
                    ),
                    MaxResults=1000,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to search EC2 transit gateway routes in route table "
                        f"{transit_gateway_route_table_id}"
                    ),
                )

            if response.get("AdditionalRoutesAvailable"):
                module.fail_json(
                    msg=(
                        "Unable to gather all EC2 transit gateway routes because the "
                        "search returned more than 1000 matching routes"
                    ),
                    transit_gateway_route_table_id=transit_gateway_route_table_id,
                )

            route_table["Routes"] = sorted(
                response.get("Routes", []), key=route_sort_key
            )

        route_tables_with_routes.append(route_table)

    module.exit_json(
        changed=False,
        transit_gateway_route_tables=boto3_resource_list_to_ansible_dict(
            route_tables_with_routes,
            transform_tags=True,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
