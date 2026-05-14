#!/usr/bin/python
# Copyright: Taylor Kimball
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    scrub_none_parameters,
)


def route_destination(route):
    return route.get("DestinationCidrBlock") or route.get("PrefixListId") or ""


def route_sort_key(route):
    return (
        route_destination(route),
        route.get("Type") or "",
        route.get("State") or "",
    )


def build_request(module):
    request = scrub_none_parameters(
        {
            "TransitGatewayRouteTableIds": module.params[
                "transit_gateway_route_table_ids"
            ]
            or None
        }
    )
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])
    return request


def search_routes(client, module, transit_gateway_route_table_id):
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

    return sorted(response.get("Routes", []), key=route_sort_key)


def add_routes_to_route_tables(client, module, route_tables):
    results = []
    for route_table in route_tables:
        route_table = dict(route_table)
        route_table["Routes"] = []

        if route_table.get("State") == "available":
            route_table["Routes"] = search_routes(
                client, module, route_table["TransitGatewayRouteTableId"]
            )

        results.append(route_table)
    return results


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

    try:
        route_tables = paginated_query_with_retries(
            client,
            "describe_transit_gateway_route_tables",
            **build_request(module),
        ).get("TransitGatewayRouteTables", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to describe EC2 transit gateway route tables"
        )

    module.exit_json(
        changed=False,
        transit_gateway_route_tables=boto3_resource_list_to_ansible_dict(
            add_routes_to_route_tables(client, module, route_tables),
            transform_tags=True,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
