#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - Required when O(transit_gateway_route_table_id) is omitted.
    type: str
  purge_routes:
    description:
      - Whether static routes not listed in O(routes) should be removed.
      - Propagated routes and routes referencing a prefix list are ignored.
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
          - Mutually exclusive with O(routes[].blackhole).
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
      - Required when O(transit_gateway_route_table_id) is omitted.
    type: str
  transit_gateway_route_table_id:
    description:
      - The transit gateway route table ID.
      - Required when O(transit_gateway_id) and O(name) are omitted.
    type: str
  wait:
    description:
      - Whether to wait for route table and route state changes to complete.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
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
    get_boto3_client_method_parameters,
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
)

ROUTE_TABLE_TERMINAL_STATES = {"deleted"}
ROUTE_DELETED_STATES = {"deleted", "deleting"}
ROUTE_PRESENT_STATES = {"active", "blackhole", "pending"}
ROUTE_STATE_ORDER = {
    "active": 0,
    "blackhole": 1,
    "pending": 2,
    "deleting": 3,
    "deleted": 4,
}


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
    name = module.params["name"]
    tags = dict(module.params["tags"] or {})

    if name:
        tags["Name"] = name

    return tags


def current_tags(route_table):
    return boto3_tag_list_to_ansible_dict((route_table or {}).get("Tags", []))


def route_sort_key(route):
    return ROUTE_STATE_ORDER.get(route.get("State"), 99)


def route_destination(route):
    return route.get("DestinationCidrBlock")


def get_route_table_by_id(client, module, transit_gateway_route_table_id):
    if not transit_gateway_route_table_id:
        return None

    try:
        route_tables = paginated_query_with_retries(
            client,
            "describe_transit_gateway_route_tables",
            TransitGatewayRouteTableIds=[transit_gateway_route_table_id],
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


def find_route_table(client, module):
    transit_gateway_route_table_id = module.params["transit_gateway_route_table_id"]
    transit_gateway_id = module.params["transit_gateway_id"]
    name = module.params["name"]

    if transit_gateway_route_table_id:
        return get_route_table_by_id(client, module, transit_gateway_route_table_id)

    filters = {"state": ["available", "pending"]}
    if transit_gateway_id:
        filters["transit-gateway-id"] = transit_gateway_id
    if name:
        filters["tag:Name"] = name

    try:
        route_tables = paginated_query_with_retries(
            client,
            "describe_transit_gateway_route_tables",
            Filters=ansible_dict_to_boto3_filter_list(filters),
        ).get("TransitGatewayRouteTables", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to describe EC2 transit gateway route tables"
        )

    if len(route_tables) > 1:
        transit_gateway_route_table_ids = []
        for route_table in route_tables:
            transit_gateway_route_table_ids.append(route_table_id(route_table))

        module.fail_json(
            msg="More than one matching EC2 transit gateway route table was found",
            transit_gateway_route_table_ids=transit_gateway_route_table_ids,
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
        route_table = get_route_table_by_id(
            client, module, transit_gateway_route_table_id
        )

        if route_table is None and absent_is_success:
            return None

        state = (route_table or {}).get("State")

        if state in desired_states:
            return route_table

        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=(
            "Timed out waiting for EC2 transit gateway route table "
            f"{transit_gateway_route_table_id}"
        ),
        state=(route_table or {}).get("State"),
        transit_gateway_route_table=normalize_route_table(route_table),
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


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

    matching_routes = []
    for route in routes:
        if route.get("Type") != "static":
            continue

        if route.get("State") == "deleted":
            continue

        matching_routes.append(route)

    routes = sorted(matching_routes, key=route_sort_key)

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

    attachment_ids = set()
    for attachment in route.get("TransitGatewayAttachments", []):
        attachment_id = attachment.get("TransitGatewayAttachmentId")

        if not attachment_id:
            continue

        attachment_ids.add(attachment_id)

    return desired.get("transit_gateway_attachment_id") in attachment_ids


def route_is_static(route):
    return (
        route is not None
        and route.get("Type") == "static"
        and route.get("State") not in ROUTE_DELETED_STATES
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
        time.sleep(module.params["wait_delay"])

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
        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=(
            "Timed out waiting for EC2 transit gateway route "
            f"{destination_cidr_block} to be removed"
        ),
        route=normalize_routes([route])[0] if route else {},
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def ensure_route_absent(
    client, module, transit_gateway_route_table_id, destination_cidr_block
):
    wait = module.params["wait"]
    route = get_route(
        client, module, transit_gateway_route_table_id, destination_cidr_block
    )

    if not route_is_static(route):
        if wait and route and route.get("State") == "deleting":
            route = wait_for_route_absent(
                client, module, transit_gateway_route_table_id, destination_cidr_block
            )
        return False, route

    if module.check_mode:
        return True, None

    try:
        client.delete_transit_gateway_route(
            DestinationCidrBlock=destination_cidr_block,
            TransitGatewayRouteTableId=transit_gateway_route_table_id,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete EC2 transit gateway route {destination_cidr_block}",
        )

    if wait:
        route = wait_for_route_absent(
            client, module, transit_gateway_route_table_id, destination_cidr_block
        )
    return True, route


def ensure_present(client, module):
    route_table_identifier = module.params["transit_gateway_route_table_id"]
    transit_gateway_id = module.params["transit_gateway_id"]
    desired_routes = module.params["routes"] or []
    purge_routes = module.params["purge_routes"]
    wait = module.params["wait"]
    route_table = find_route_table(client, module)

    changed = False

    if route_table is None:
        if route_table_identifier:
            module.fail_json(
                msg=(
                    "EC2 transit gateway route table "
                    f"{route_table_identifier} does not exist"
                ),
                transit_gateway_route_table_id=route_table_identifier,
            )
        changed = True
        if module.check_mode:
            route_table = {
                "State": "available",
                "Tags": ansible_dict_to_boto3_tag_list(desired_tags(module)),
                "TransitGatewayId": transit_gateway_id,
                "TransitGatewayRouteTableId": route_table_identifier or "",
            }
        else:
            request = {"TransitGatewayId": transit_gateway_id}
            tag_specs = boto3_tag_specifications(
                desired_tags(module), types="transit-gateway-route-table"
            )
            if tag_specs is not None:
                request["TagSpecifications"] = tag_specs

            try:
                route_table = client.create_transit_gateway_route_table(
                    **request, aws_retry=True
                ).get("TransitGatewayRouteTable")
            except Exception as e:
                module.fail_json_aws(
                    e, msg="Unable to create EC2 transit gateway route table"
                )

            if wait:
                route_table = wait_for_route_table(
                    client, module, route_table_id(route_table), {"available"}
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
    elif route_table.get("State") == "pending" and wait:
        route_table = wait_for_route_table(
            client, module, route_table_id(route_table), {"available"}
        )

    tags = module.params["tags"]
    desired_route_table_tags = desired_tags(module)

    if desired_route_table_tags or tags is not None:
        purge_tags = module.params["purge_tags"] if tags is not None else False
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current_tags(route_table),
            desired_route_table_tags,
            purge_tags=purge_tags,
        )

        tag_changed = bool(tags_to_set or tag_keys_to_unset)

        if tag_changed:
            if not module.check_mode:
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
                                "Unable to remove tags from EC2 transit gateway "
                                f"route table {resource_id}"
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
                            e,
                            msg=(
                                "Unable to tag EC2 transit gateway route table "
                                f"{resource_id}"
                            ),
                        )

            route_table = dict(route_table)
            current = current_tags(route_table)
            for tag_key in tag_keys_to_unset:
                current.pop(tag_key, None)

            current.update(tags_to_set)
            route_table["Tags"] = ansible_dict_to_boto3_tag_list(current)

        changed = changed or tag_changed

    route_changed = False
    routes = None
    if desired_routes or purge_routes:
        routes = []
        transit_gateway_route_table_id = route_table_id(route_table)

        if module.check_mode and not transit_gateway_route_table_id:
            for desired_route in desired_routes:
                if desired_route.get("state", "present") != "present":
                    continue

                routes.append(check_mode_route(desired_route))

            route_changed = bool(desired_routes)
        else:
            for desired_route in desired_routes:
                if desired_route.get("state", "present") == "absent":
                    current_route_changed, current_route = ensure_route_absent(
                        client,
                        module,
                        transit_gateway_route_table_id,
                        desired_route["destination_cidr_block"],
                    )
                else:
                    destination_cidr_block = desired_route["destination_cidr_block"]
                    current_route = get_route(
                        client,
                        module,
                        transit_gateway_route_table_id,
                        destination_cidr_block,
                    )
                    if current_route and current_route.get("State") == "deleting":
                        if not wait:
                            module.fail_json(
                                msg=(
                                    "EC2 transit gateway route "
                                    f"{destination_cidr_block} is deleting"
                                ),
                                route=normalize_routes([current_route])[0],
                                transit_gateway_route_table_id=(
                                    transit_gateway_route_table_id
                                ),
                            )
                        wait_for_route_absent(
                            client,
                            module,
                            transit_gateway_route_table_id,
                            destination_cidr_block,
                        )
                        current_route = None

                    if desired_route_matches(current_route, desired_route):
                        current_route_changed = False
                        if wait and current_route.get("State") == "pending":
                            current_route = wait_for_route(
                                client,
                                module,
                                transit_gateway_route_table_id,
                                desired_route,
                            )
                    elif module.check_mode:
                        current_route_changed = True
                        current_route = check_mode_route(desired_route)
                    else:
                        request = {
                            "DestinationCidrBlock": destination_cidr_block,
                            "TransitGatewayRouteTableId": (
                                transit_gateway_route_table_id
                            ),
                        }
                        if desired_route.get("blackhole"):
                            request["Blackhole"] = True
                        else:
                            request["TransitGatewayAttachmentId"] = desired_route[
                                "transit_gateway_attachment_id"
                            ]

                        current_route_changed = True
                        if (
                            current_route is None
                            or current_route.get("State") == "deleted"
                        ):
                            try:
                                current_route = client.create_transit_gateway_route(
                                    **request,
                                    aws_retry=True,
                                ).get("Route")
                            except Exception as e:
                                module.fail_json_aws(
                                    e,
                                    msg=(
                                        "Unable to create EC2 transit gateway route "
                                        f"{destination_cidr_block}"
                                    ),
                                )

                        else:
                            try:
                                current_route = client.replace_transit_gateway_route(
                                    **request,
                                    aws_retry=True,
                                ).get("Route")
                            except Exception as e:
                                module.fail_json_aws(
                                    e,
                                    msg=(
                                        "Unable to replace EC2 transit gateway route "
                                        f"{destination_cidr_block}"
                                    ),
                                )

                        if wait:
                            current_route = wait_for_route(
                                client,
                                module,
                                transit_gateway_route_table_id,
                                desired_route,
                            )

                route_changed = route_changed or current_route_changed
                if current_route:
                    routes.append(current_route)

            if purge_routes:
                desired_destinations = set()
                for desired_route in desired_routes:
                    if desired_route.get("state", "present") != "present":
                        continue

                    desired_destinations.add(desired_route["destination_cidr_block"])

                purged_any = False
                for current_route in static_routes(
                    client, module, transit_gateway_route_table_id
                ):
                    if not route_destination(current_route):
                        continue

                    if route_destination(current_route) in desired_destinations:
                        continue

                    purged_route_changed = ensure_route_absent(
                        client,
                        module,
                        transit_gateway_route_table_id,
                        route_destination(current_route),
                    )[0]
                    purged_any = purged_any or purged_route_changed

                route_changed = route_changed or purged_any

                if purged_any and not module.check_mode:
                    routes = static_routes(
                        client, module, transit_gateway_route_table_id
                    )
    changed = changed or route_changed

    exit_module(module, changed, route_table, routes=routes)


def ensure_absent(client, module):
    wait = module.params["wait"]
    route_table = find_route_table(client, module)

    if route_table is None or route_table.get("State") in ROUTE_TABLE_TERMINAL_STATES:
        exit_module(module, False, route_table)

    if route_table.get("State") == "deleting":
        if wait:
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

    transit_gateway_route_table_id = route_table_id(route_table)

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

    if wait:
        route_table = wait_for_route_table(
            client,
            module,
            transit_gateway_route_table_id,
            {"deleted"},
            absent_is_success=True,
        )
    exit_module(module, changed, route_table)


def exit_module(module, changed, route_table, routes=None):
    result = {
        "changed": changed,
        "state": module.params["state"],
    }
    if route_table:
        result["transit_gateway_route_table"] = normalize_route_table(route_table)
    if route_table_id(route_table):
        result["transit_gateway_route_table_id"] = route_table_id(route_table)
    if routes is not None:
        result["routes"] = normalize_routes(routes)
    module.exit_json(**result)


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
            "mutually_exclusive": [["blackhole", "transit_gateway_attachment_id"]],
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
        required_one_of=[
            ["transit_gateway_route_table_id", "transit_gateway_id"],
            ["transit_gateway_route_table_id", "name"],
        ],
        supports_check_mode=True,
    )

    if module.params["wait"]:
        if module.params["wait_delay"] < 1:
            module.fail_json(msg="wait_delay must be 1 or greater")

        if module.params["wait_timeout"] < 1:
            module.fail_json(msg="wait_timeout must be 1 or greater")

    state = module.params["state"]
    purge_routes = module.params["purge_routes"]
    routes = module.params["routes"]
    has_absent_route = False
    has_attachment_route = False
    has_blackhole_route = False
    has_present_route = False

    destinations = set()
    for route in routes or []:
        if route["destination_cidr_block"] in destinations:
            module.fail_json(
                msg="routes[].destination_cidr_block values must be unique",
                destination_cidr_block=route["destination_cidr_block"],
            )
        destinations.add(route["destination_cidr_block"])

        if route.get("state", "present") == "absent":
            has_absent_route = True
            continue

        has_present_route = True
        if route.get("blackhole"):
            has_blackhole_route = True
        elif route.get("transit_gateway_attachment_id"):
            has_attachment_route = True
        else:
            module.fail_json(
                msg=(
                    "routes[].transit_gateway_attachment_id is required when "
                    "routes[].state=present and routes[].blackhole is not true"
                ),
                destination_cidr_block=route["destination_cidr_block"],
            )

    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    method_names = {
        "describe_transit_gateway_route_tables",
    }
    if state == "present":
        if not module.params["transit_gateway_route_table_id"]:
            method_names.add("create_transit_gateway_route_table")
        if desired_tags(module):
            method_names.add("create_tags")
        if module.params["tags"] is not None and module.params["purge_tags"]:
            method_names.add("delete_tags")
        if routes or purge_routes:
            method_names.add("search_transit_gateway_routes")
        if has_present_route:
            method_names.add("create_transit_gateway_route")
            method_names.add("replace_transit_gateway_route")
        if has_absent_route or purge_routes:
            method_names.add("delete_transit_gateway_route")

    if state == "absent":
        method_names.add("delete_transit_gateway_route_table")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support EC2 {method_name}"
            )

    required_method_parameters = {
        "create_tags": ("Resources", "Tags"),
        "create_transit_gateway_route": (
            "DestinationCidrBlock",
            "TransitGatewayRouteTableId",
        ),
        "create_transit_gateway_route_table": (
            "TransitGatewayId",
            "TagSpecifications",
        ),
        "delete_tags": ("Resources", "Tags"),
        "delete_transit_gateway_route": (
            "DestinationCidrBlock",
            "TransitGatewayRouteTableId",
        ),
        "delete_transit_gateway_route_table": ("TransitGatewayRouteTableId",),
        "describe_transit_gateway_route_tables": (
            "Filters",
            "TransitGatewayRouteTableIds",
        ),
        "replace_transit_gateway_route": (
            "DestinationCidrBlock",
            "TransitGatewayRouteTableId",
        ),
        "search_transit_gateway_routes": (
            "Filters",
            "MaxResults",
            "TransitGatewayRouteTableId",
        ),
    }
    if has_blackhole_route:
        required_method_parameters["create_transit_gateway_route"] += ("Blackhole",)
        required_method_parameters["replace_transit_gateway_route"] += ("Blackhole",)
    if has_attachment_route:
        required_method_parameters["create_transit_gateway_route"] += (
            "TransitGatewayAttachmentId",
        )
        required_method_parameters["replace_transit_gateway_route"] += (
            "TransitGatewayAttachmentId",
        )

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in set(parameter_names):
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support EC2 "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
