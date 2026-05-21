#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_transit_gateway_route_table
short_description: Manage EC2 transit gateway route tables
description:
  - Creates and deletes AWS EC2 transit gateway route tables.
  - Manages route table tags.
  - Manages static transit gateway routes in the route table.
  - This module does not manage route table associations or propagations.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The route table name.
      - This value is managed as the C(Name) tag.
      - Required with O(transit_gateway_id) when creating a route table.
      - When O(transit_gateway_route_table_id) is omitted, this is used with
        O(transit_gateway_id) to find the route table.
    type: str
  purge_routes:
    description:
      - Whether static routes not listed in O(routes) should be removed.
      - Propagated routes are ignored.
    default: false
    type: bool
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - When O(name) is provided without O(tags), existing tags other than
        C(Name) are retained.
    default: true
    type: bool
  routes:
    description:
      - Static transit gateway routes to manage in the route table.
    elements: dict
    suboptions:
      blackhole:
        description:
          - Whether to create a blackhole route.
          - Mutually exclusive with O(routes[].transit_gateway_attachment_id).
        default: false
        type: bool
      destination_cidr_block:
        description:
          - The destination CIDR block for the route.
        required: true
        type: str
      state:
        description:
          - Whether the static route should exist.
        choices:
          - absent
          - present
        default: present
        type: str
      transit_gateway_attachment_id:
        description:
          - The transit gateway attachment ID to route traffic to.
          - Required when O(routes[].state=present) unless
            O(routes[].blackhole=true).
        type: str
    type: list
  state:
    description:
      - Whether the route table should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the route table.
      - If omitted and O(name) is not set, existing tags are not modified.
    type: dict
  transit_gateway_id:
    description:
      - The transit gateway ID for the route table.
      - Required with O(name) when creating a route table.
    type: str
  transit_gateway_route_table_id:
    description:
      - The transit gateway route table ID.
    type: str
  wait:
    description:
      - Whether to wait for route table and route state changes to complete.
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
    default: 600
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a transit gateway route table is present
  linuxhq.aws.ec2_transit_gateway_route_table:
    name: example
    transit_gateway_id: tgw-0123456789abcdef0
    tags:
      Environment: test

- name: Ensure static routes are present
  linuxhq.aws.ec2_transit_gateway_route_table:
    name: example
    transit_gateway_id: tgw-0123456789abcdef0
    routes:
      - destination_cidr_block: 10.10.0.0/16
        transit_gateway_attachment_id: tgw-attach-0123456789abcdef0
      - destination_cidr_block: 10.20.0.0/16
        blackhole: true

- name: Ensure a static route is absent
  linuxhq.aws.ec2_transit_gateway_route_table:
    transit_gateway_route_table_id: tgw-rtb-0123456789abcdef0
    routes:
      - destination_cidr_block: 10.10.0.0/16
        state: absent

- name: Ensure a transit gateway route table is absent
  linuxhq.aws.ec2_transit_gateway_route_table:
    transit_gateway_route_table_id: tgw-rtb-0123456789abcdef0
    state: absent
"""

RETURN = r"""
routes:
  description:
    - The matching static routes after module execution.
  returned: when route management is requested
  type: list
  elements: dict
state:
  description:
    - The requested route table state.
  returned: always
  type: str
transit_gateway_route_table:
  description:
    - The transit gateway route table after module execution.
  returned: when the route table exists
  type: dict
transit_gateway_route_table_id:
  description:
    - The transit gateway route table ID.
  returned: when the route table exists
  type: str
"""

import time

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    boto3_tag_specifications,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

ROUTE_TABLE_TERMINAL_STATES = {"deleted"}
ROUTE_DELETED_STATES = {"deleted", "deleting"}
ROUTE_PRESENT_STATES = {"active", "blackhole", "pending"}


def route_table_id(route_table):
    return (route_table or {}).get("TransitGatewayRouteTableId")


def normalize_route_table(route_table):
    return boto3_resource_to_ansible_dict(
        route_table or {}, transform_tags=True, force_tags=False
    )


def normalize_routes(routes):
    return boto3_resource_list_to_ansible_dict(
        routes or [], transform_tags=False, force_tags=False
    )


def desired_tags(module):
    tags = dict(module.params["tags"] or {})
    if module.params["name"]:
        tags["Name"] = module.params["name"]
    return tags


def current_tags(route_table):
    return boto3_tag_list_to_ansible_dict((route_table or {}).get("Tags", []))


def route_attachment_ids(route):
    return {
        attachment.get("TransitGatewayAttachmentId")
        for attachment in route.get("TransitGatewayAttachments", [])
        if attachment.get("TransitGatewayAttachmentId")
    }


def route_sort_key(route):
    state_order = {
        "active": 0,
        "blackhole": 1,
        "pending": 2,
        "deleting": 3,
        "deleted": 4,
    }
    return state_order.get(route.get("State"), 99)


def route_destination(route):
    return route.get("DestinationCidrBlock")


def present_route_destinations(module):
    return {
        route["destination_cidr_block"]
        for route in module.params["routes"] or []
        if route.get("state", "present") == "present"
    }


def get_route_table(client, module, transit_gateway_route_table_id):
    if not transit_gateway_route_table_id:
        return None
    try:
        route_tables = client.describe_transit_gateway_route_tables(
            TransitGatewayRouteTableIds=[transit_gateway_route_table_id],
            aws_retry=True,
        ).get("TransitGatewayRouteTables", [])
    except is_boto3_error_code("InvalidTransitGatewayRouteTableID.NotFound"):
        return None
    except is_boto3_error_code("InvalidRouteTableID.NotFound"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to describe EC2 transit gateway route table "
                f"{transit_gateway_route_table_id}"
            ),
        )
    return route_tables[0] if route_tables else None


def describe_route_tables(client, module, filters):
    try:
        return paginated_query_with_retries(
            client,
            "describe_transit_gateway_route_tables",
            Filters=ansible_dict_to_boto3_filter_list(filters),
        ).get("TransitGatewayRouteTables", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to describe EC2 transit gateway route tables"
        )


def find_route_table(client, module):
    if module.params["transit_gateway_route_table_id"]:
        return get_route_table(
            client, module, module.params["transit_gateway_route_table_id"]
        )

    filters = {"state": ["available", "pending"]}
    if module.params["transit_gateway_id"]:
        filters["transit-gateway-id"] = module.params["transit_gateway_id"]
    if module.params["name"]:
        filters["tag:Name"] = module.params["name"]

    route_tables = describe_route_tables(client, module, filters)
    if len(route_tables) > 1:
        module.fail_json(
            msg="More than one matching EC2 transit gateway route table was found",
            transit_gateway_route_table_ids=[
                route_table_id(route_table) for route_table in route_tables
            ],
        )
    return route_tables[0] if route_tables else None


def wait_for_route_table(
    client,
    module,
    transit_gateway_route_table_id,
    desired_states,
    absent_is_success=False,
):
    deadline = time.monotonic() + module.params["wait_timeout"]
    route_table = {}

    while time.monotonic() < deadline:
        route_table = get_route_table(client, module, transit_gateway_route_table_id)
        if route_table is None and absent_is_success:
            return None
        state = (route_table or {}).get("State")
        if state in desired_states:
            return route_table
        time.sleep(max(1, module.params["wait_delay"]))

    module.fail_json(
        msg=(
            "Timed out waiting for EC2 transit gateway route table "
            f"{transit_gateway_route_table_id}"
        ),
        state=(route_table or {}).get("State"),
        transit_gateway_route_table=normalize_route_table(route_table),
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def create_route_table(client, module):
    request = scrub_none_parameters(
        {
            "TransitGatewayId": module.params["transit_gateway_id"],
            "TagSpecifications": boto3_tag_specifications(
                desired_tags(module), types="transit-gateway-route-table"
            ),
        }
    )
    try:
        route_table = client.create_transit_gateway_route_table(
            **request, aws_retry=True
        ).get("TransitGatewayRouteTable")
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to create EC2 transit gateway route table")

    if module.params["wait"]:
        route_table = wait_for_route_table(
            client, module, route_table_id(route_table), {"available"}
        )
    return route_table


def delete_route_table(client, module, transit_gateway_route_table_id):
    try:
        route_table = client.delete_transit_gateway_route_table(
            TransitGatewayRouteTableId=transit_gateway_route_table_id,
            aws_retry=True,
        ).get("TransitGatewayRouteTable")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to delete EC2 transit gateway route table "
                f"{transit_gateway_route_table_id}"
            ),
        )
    if module.params["wait"]:
        route_table = wait_for_route_table(
            client,
            module,
            transit_gateway_route_table_id,
            {"deleted"},
            absent_is_success=True,
        )
    return route_table


def check_mode_route_table(module, state="available"):
    route_table = {
        "State": state,
        "Tags": ansible_dict_to_boto3_tag_list(desired_tags(module)),
        "TransitGatewayId": module.params["transit_gateway_id"],
        "TransitGatewayRouteTableId": module.params["transit_gateway_route_table_id"]
        or "",
    }
    return route_table


def check_mode_tags(module, route_table):
    if not desired_tags(module):
        return route_table
    route_table = dict(route_table)
    tags = current_tags(route_table)
    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        tags,
        desired_tags(module),
        purge_tags=(
            module.params["purge_tags"] if module.params["tags"] is not None else False
        ),
    )
    for key in tag_keys_to_unset:
        tags.pop(key, None)
    tags.update(tags_to_set)
    route_table["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return route_table


def ensure_tags(client, module, route_table):
    tags = desired_tags(module)
    if not tags:
        return False, route_table

    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        current_tags(route_table),
        tags,
        purge_tags=(
            module.params["purge_tags"] if module.params["tags"] is not None else False
        ),
    )
    changed = bool(tags_to_set or tag_keys_to_unset)
    if module.check_mode:
        return changed, check_mode_tags(module, route_table)

    resource_id = route_table_id(route_table)
    if tag_keys_to_unset:
        try:
            client.delete_tags(
                Resources=[resource_id],
                Tags=[{"Key": key} for key in tag_keys_to_unset],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to remove tags from EC2 transit gateway route table "
                    f"{resource_id}"
                ),
            )
    if tags_to_set:
        try:
            client.create_tags(
                Resources=[resource_id],
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to tag EC2 transit gateway route table {resource_id}"
            )

    if changed:
        route_table = dict(route_table)
        current = current_tags(route_table)
        for tag_key in tag_keys_to_unset:
            current.pop(tag_key, None)
        current.update(tags_to_set)
        route_table["Tags"] = ansible_dict_to_boto3_tag_list(current)
    return changed, route_table


def search_routes(client, module, transit_gateway_route_table_id, filters):
    try:
        response = client.search_transit_gateway_routes(
            TransitGatewayRouteTableId=transit_gateway_route_table_id,
            Filters=ansible_dict_to_boto3_filter_list(filters),
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
                "Unable to manage EC2 transit gateway routes because the search "
                "returned more than 1000 matching routes"
            ),
            transit_gateway_route_table_id=transit_gateway_route_table_id,
        )
    return response.get("Routes", [])


def get_route(client, module, transit_gateway_route_table_id, destination_cidr_block):
    routes = search_routes(
        client,
        module,
        transit_gateway_route_table_id,
        {"route-search.exact-match": destination_cidr_block},
    )
    routes = sorted(
        [
            route
            for route in routes
            if route.get("Type") == "static" and route.get("State") != "deleted"
        ],
        key=route_sort_key,
    )
    return routes[0] if routes else None


def static_routes(client, module, transit_gateway_route_table_id):
    return sorted(
        search_routes(
            client,
            module,
            transit_gateway_route_table_id,
            {"type": "static"},
        ),
        key=lambda route: route_destination(route) or "",
    )


def desired_route_matches(route, desired):
    if route is None or route.get("Type") != "static":
        return False
    if route.get("State") not in ROUTE_PRESENT_STATES:
        return False
    if desired.get("blackhole"):
        return route.get("State") == "blackhole"
    return desired.get("transit_gateway_attachment_id") in route_attachment_ids(route)


def route_is_static(route):
    return (
        route is not None
        and route.get("Type") == "static"
        and route.get("State") not in ROUTE_DELETED_STATES
    )


def route_request(transit_gateway_route_table_id, desired):
    request = {
        "DestinationCidrBlock": desired["destination_cidr_block"],
        "TransitGatewayRouteTableId": transit_gateway_route_table_id,
    }
    if desired.get("blackhole"):
        request["Blackhole"] = True
    else:
        request["TransitGatewayAttachmentId"] = desired["transit_gateway_attachment_id"]
    return request


def create_route(client, module, transit_gateway_route_table_id, desired):
    request = route_request(transit_gateway_route_table_id, desired)
    try:
        return client.create_transit_gateway_route(
            **request,
            aws_retry=True,
        ).get("Route")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to create EC2 transit gateway route "
                f"{desired['destination_cidr_block']}"
            ),
        )


def replace_route(client, module, transit_gateway_route_table_id, desired):
    request = route_request(transit_gateway_route_table_id, desired)
    try:
        return client.replace_transit_gateway_route(
            **request,
            aws_retry=True,
        ).get("Route")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to replace EC2 transit gateway route "
                f"{desired['destination_cidr_block']}"
            ),
        )


def delete_route(
    client, module, transit_gateway_route_table_id, destination_cidr_block
):
    try:
        return client.delete_transit_gateway_route(
            DestinationCidrBlock=destination_cidr_block,
            TransitGatewayRouteTableId=transit_gateway_route_table_id,
            aws_retry=True,
        ).get("Route")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete EC2 transit gateway route {destination_cidr_block}",
        )


def check_mode_route(desired):
    route = {
        "DestinationCidrBlock": desired["destination_cidr_block"],
        "State": "blackhole" if desired.get("blackhole") else "active",
        "TransitGatewayAttachments": [],
        "Type": "static",
    }
    if desired.get("transit_gateway_attachment_id"):
        route["TransitGatewayAttachments"] = [
            {
                "TransitGatewayAttachmentId": desired["transit_gateway_attachment_id"],
            }
        ]
    return route


def wait_for_route(client, module, transit_gateway_route_table_id, desired):
    deadline = time.monotonic() + module.params["wait_timeout"]
    route = {}

    while time.monotonic() < deadline:
        route = get_route(
            client,
            module,
            transit_gateway_route_table_id,
            desired["destination_cidr_block"],
        )
        if desired_route_matches(route, desired) and route.get("State") in (
            "active",
            "blackhole",
        ):
            return route
        time.sleep(max(1, module.params["wait_delay"]))

    module.fail_json(
        msg=(
            "Timed out waiting for EC2 transit gateway route "
            f"{desired['destination_cidr_block']}"
        ),
        route=normalize_routes([route])[0] if route else {},
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def wait_for_route_absent(
    client, module, transit_gateway_route_table_id, destination_cidr_block
):
    deadline = time.monotonic() + module.params["wait_timeout"]
    route = {}

    while time.monotonic() < deadline:
        route = get_route(
            client, module, transit_gateway_route_table_id, destination_cidr_block
        )
        if not route_is_static(route):
            return route
        time.sleep(max(1, module.params["wait_delay"]))

    module.fail_json(
        msg=(
            "Timed out waiting for EC2 transit gateway route "
            f"{destination_cidr_block} to be removed"
        ),
        route=normalize_routes([route])[0] if route else {},
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def ensure_route_present(client, module, transit_gateway_route_table_id, desired):
    route = get_route(
        client,
        module,
        transit_gateway_route_table_id,
        desired["destination_cidr_block"],
    )
    if route and route.get("State") == "deleting":
        if not module.params["wait"]:
            module.fail_json(
                msg=(
                    "EC2 transit gateway route "
                    f"{desired['destination_cidr_block']} is deleting"
                ),
                route=normalize_routes([route])[0],
                transit_gateway_route_table_id=transit_gateway_route_table_id,
            )
        wait_for_route_absent(
            client,
            module,
            transit_gateway_route_table_id,
            desired["destination_cidr_block"],
        )
        route = None

    if desired_route_matches(route, desired):
        if module.params["wait"] and route.get("State") == "pending":
            route = wait_for_route(
                client, module, transit_gateway_route_table_id, desired
            )
        return False, route

    if module.check_mode:
        return True, check_mode_route(desired)

    if route is None or route.get("State") == "deleted":
        route = create_route(client, module, transit_gateway_route_table_id, desired)
    else:
        route = replace_route(client, module, transit_gateway_route_table_id, desired)

    if module.params["wait"]:
        route = wait_for_route(client, module, transit_gateway_route_table_id, desired)
    return True, route


def ensure_route_absent(
    client, module, transit_gateway_route_table_id, destination_cidr_block
):
    route = get_route(
        client, module, transit_gateway_route_table_id, destination_cidr_block
    )
    if not route_is_static(route):
        if module.params["wait"] and route and route.get("State") == "deleting":
            route = wait_for_route_absent(
                client, module, transit_gateway_route_table_id, destination_cidr_block
            )
        return False, route

    if module.check_mode:
        return True, None

    delete_route(client, module, transit_gateway_route_table_id, destination_cidr_block)
    if module.params["wait"]:
        route = wait_for_route_absent(
            client, module, transit_gateway_route_table_id, destination_cidr_block
        )
    return True, route


def manage_routes(client, module, transit_gateway_route_table_id):
    if module.check_mode and not transit_gateway_route_table_id:
        return bool(module.params["routes"]), [
            check_mode_route(route)
            for route in module.params["routes"] or []
            if route.get("state", "present") == "present"
        ]

    changed = False
    routes = []
    for route in module.params["routes"] or []:
        if route.get("state", "present") == "absent":
            route_changed, current_route = ensure_route_absent(
                client,
                module,
                transit_gateway_route_table_id,
                route["destination_cidr_block"],
            )
        else:
            route_changed, current_route = ensure_route_present(
                client, module, transit_gateway_route_table_id, route
            )
        changed = changed or route_changed
        if current_route:
            routes.append(current_route)

    if module.params["purge_routes"]:
        desired_destinations = present_route_destinations(module)
        for route in static_routes(client, module, transit_gateway_route_table_id):
            if route_destination(route) in desired_destinations:
                continue
            route_changed, _ = ensure_route_absent(
                client,
                module,
                transit_gateway_route_table_id,
                route_destination(route),
            )
            changed = changed or route_changed

    if module.params["purge_routes"] and not module.check_mode:
        routes = static_routes(client, module, transit_gateway_route_table_id)
    return changed, routes


def ensure_present(client, module):
    route_table = find_route_table(client, module)
    changed = False

    if route_table is None:
        if module.params["transit_gateway_route_table_id"]:
            module.fail_json(
                msg=(
                    "EC2 transit gateway route table "
                    f"{module.params['transit_gateway_route_table_id']} does not exist"
                ),
                transit_gateway_route_table_id=module.params[
                    "transit_gateway_route_table_id"
                ],
            )
        changed = True
        route_table = (
            check_mode_route_table(module)
            if module.check_mode
            else create_route_table(client, module)
        )
    elif route_table.get("State") == "deleted":
        module.fail_json(
            msg=(
                "EC2 transit gateway route table "
                f"{route_table_id(route_table)} is deleted"
            ),
            transit_gateway_route_table=normalize_route_table(route_table),
            transit_gateway_route_table_id=route_table_id(route_table),
        )
    elif route_table.get("State") == "deleting":
        module.fail_json(
            msg=(
                "EC2 transit gateway route table "
                f"{route_table_id(route_table)} is deleting"
            ),
            transit_gateway_route_table=normalize_route_table(route_table),
            transit_gateway_route_table_id=route_table_id(route_table),
        )
    elif route_table.get("State") == "pending" and module.params["wait"]:
        route_table = wait_for_route_table(
            client, module, route_table_id(route_table), {"available"}
        )

    tag_changed, route_table = ensure_tags(client, module, route_table)
    changed = changed or tag_changed

    route_changed = False
    routes = []
    if module.params["routes"] or module.params["purge_routes"]:
        route_changed, routes = manage_routes(
            client, module, route_table_id(route_table)
        )
    changed = changed or route_changed

    exit_module(module, changed, route_table, routes=routes)


def ensure_absent(client, module):
    route_table = find_route_table(client, module)
    if route_table is None or route_table.get("State") in ROUTE_TABLE_TERMINAL_STATES:
        exit_module(module, False, route_table)

    if route_table.get("State") == "deleting":
        if module.params["wait"]:
            route_table = wait_for_route_table(
                client,
                module,
                route_table_id(route_table),
                {"deleted"},
                absent_is_success=True,
            )
        exit_module(module, False, route_table)

    changed = True
    if module.check_mode:
        exit_module(module, changed, dict(route_table, State="deleted"))

    route_table = delete_route_table(client, module, route_table_id(route_table))
    exit_module(module, changed, route_table)


def exit_module(module, changed, route_table, routes=None):
    result = {
        "changed": changed,
        "state": module.params["state"],
        "transit_gateway_route_table": normalize_route_table(route_table),
    }
    if route_table_id(route_table):
        result["transit_gateway_route_table_id"] = route_table_id(route_table)
    if routes is not None:
        result["routes"] = normalize_routes(routes)
    module.exit_json(**result)


def validate_routes(module):
    destinations = set()
    for route in module.params["routes"] or []:
        if route["destination_cidr_block"] in destinations:
            module.fail_json(
                msg="routes[].destination_cidr_block values must be unique",
                destination_cidr_block=route["destination_cidr_block"],
            )
        destinations.add(route["destination_cidr_block"])

        if route.get("state", "present") == "absent":
            continue
        if route.get("blackhole") and route.get("transit_gateway_attachment_id"):
            module.fail_json(
                msg=(
                    "routes[].blackhole and routes[].transit_gateway_attachment_id "
                    "are mutually exclusive"
                ),
                destination_cidr_block=route["destination_cidr_block"],
            )
        if not route.get("blackhole") and not route.get(
            "transit_gateway_attachment_id"
        ):
            module.fail_json(
                msg=(
                    "routes[].transit_gateway_attachment_id is required when "
                    "routes[].state=present and routes[].blackhole is not true"
                ),
                destination_cidr_block=route["destination_cidr_block"],
            )


def validate_params(module):
    if module.params["state"] == "present" and not (
        module.params["transit_gateway_route_table_id"]
        or (module.params["transit_gateway_id"] and module.params["name"])
    ):
        module.fail_json(
            msg=(
                "state=present requires transit_gateway_route_table_id or "
                "both transit_gateway_id and name"
            )
        )
    if module.params["state"] == "absent" and not (
        module.params["transit_gateway_route_table_id"]
        or (module.params["transit_gateway_id"] and module.params["name"])
    ):
        module.fail_json(
            msg=(
                "state=absent requires transit_gateway_route_table_id or both "
                "transit_gateway_id and name"
            )
        )
    validate_routes(module)


def main():
    argument_spec = {
        "name": {"type": "str"},
        "purge_routes": {"default": False, "type": "bool"},
        "purge_tags": {"default": True, "type": "bool"},
        "routes": {
            "elements": "dict",
            "options": {
                "blackhole": {"default": False, "type": "bool"},
                "destination_cidr_block": {"required": True, "type": "str"},
                "state": {
                    "choices": ["absent", "present"],
                    "default": "present",
                    "type": "str",
                },
                "transit_gateway_attachment_id": {"type": "str"},
            },
            "type": "list",
        },
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"type": "dict"},
        "transit_gateway_id": {"type": "str"},
        "transit_gateway_route_table_id": {"type": "str"},
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 5, "type": "int"},
        "wait_timeout": {"default": 600, "type": "int"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    validate_params(module)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
