#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_transit_gateway_route_table
version_added: "1.9.0"
short_description: Manage EC2 transit gateway route tables
description:
  - Creates and deletes AWS EC2 transit gateway route tables.
  - Manages route table tags.
  - Manages static transit gateway routes in the route table.
  - This module does not manage route table associations or propagations.
  - EC2 permits at most 50 tags on a transit gateway route table; tag keys may
    contain at most 127 characters and tag values at most 256 characters.
  - Existing tags are purged only when O(tags) is provided and
    O(purge_tags=true). When O(name) is provided without O(tags), existing tags
    other than C(Name) are retained.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The route table name.
      - This value is managed as the C(Name) tag.
      - When O(tags) contains C(Name), its value must match this value.
      - Required when O(transit_gateway_route_table_id) is omitted.
    type: str
  purge_routes:
    description:
      - Whether static routes not listed in O(routes) should be removed.
      - Ignored unless O(routes) is supplied.
      - Routes with O(routes[].state=absent) do not count as listed, so a
        O(routes) list that contains only absent routes removes every static
        route when O(purge_routes=true).
      - Propagated routes and routes referencing a prefix list are ignored.
      - Requires botocore 1.42.37 or later.
    default: true
    type: bool
  routes:
    description:
      - Static transit gateway routes to manage in the route table.
      - Requires botocore 1.42.37 or later.
    elements: dict
    suboptions:
      blackhole:
        description:
          - Whether to create a blackhole route.
          - When omitted, this behaves as C(false).
          - When true, mutually exclusive with
            O(routes[].transit_gateway_attachment_id).
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
          - Mutually exclusive with O(routes[].blackhole=true).
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
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts route-table, route, and tag changes without modifying AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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
    purge_routes: false
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
    - The static routes for the destinations in O(routes) after module execution.
  returned: when O(routes) is supplied
  type: list
  elements: dict
  contains:
    destination_cidr_block:
      description: The destination CIDR block for the route.
      returned: when the route has a CIDR destination
      type: str
      sample: 10.10.0.0/16
    prefix_list_id:
      description: The prefix list ID used as the route destination.
      returned: when the route has a prefix list destination
      type: str
    state:
      description: The route state.
      returned: always
      type: str
      sample: active
    transit_gateway_attachments:
      description: The attachments that the route sends traffic to.
      returned: when the route has attachments
      type: list
      elements: dict
      contains:
        resource_id:
          description: The ID of the attached resource.
          returned: always
          type: str
        resource_type:
          description: The type of the attached resource.
          returned: always
          type: str
          sample: vpc
        transit_gateway_attachment_id:
          description: The transit gateway attachment ID.
          returned: always
          type: str
          sample: tgw-attach-0123456789abcdef0
    transit_gateway_route_table_announcement_id:
      description: The transit gateway route table announcement ID.
      returned: when the route is from a route table announcement
      type: str
    type:
      description: The route type.
      returned: always
      type: str
      sample: static
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
  contains:
    creation_time:
      description: The time the route table was created.
      returned: always, except for a create predicted in check mode
      type: str
    default_association_route_table:
      description: Whether this is the default association route table for the transit gateway.
      returned: always, except for a create predicted in check mode
      type: bool
    default_propagation_route_table:
      description: Whether this is the default propagation route table for the transit gateway.
      returned: always, except for a create predicted in check mode
      type: bool
    state:
      description: The route table state.
      returned: always
      type: str
      sample: available
    tags:
      description: The route table tags.
      returned: when returned by EC2, or when the module applies or predicts tag changes
      type: dict
    transit_gateway_id:
      description: The transit gateway ID.
      returned: always
      type: str
      sample: tgw-0123456789abcdef0
    transit_gateway_route_table_id:
      description: The transit gateway route table ID.
      returned: always
      type: str
      sample: tgw-rtb-0123456789abcdef0
transit_gateway_route_table_id:
  description:
    - The transit gateway route table ID.
  returned: when the route table exists
  type: str
"""

import ipaddress
import time

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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_ec2_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
)

ROUTE_TABLE_TERMINAL_STATES = {"deleted"}
ROUTE_TABLE_DELETED_STATES = {"deleted", "deleting"}
ROUTE_DELETED_STATES = {"deleted", "deleting"}
ROUTE_PRESENT_STATES = {"active", "blackhole", "pending"}
ROUTE_STATE_ORDER = {
    "active": 0,
    "blackhole": 1,
    "pending": 2,
    "deleting": 3,
}


def route_table_id(route_table):
    return route_table.get("TransitGatewayRouteTableId") if isinstance(route_table, dict) else None


def validated_route_table(module, route_table, changed=False):
    if (
        not isinstance(route_table, dict)
        or not isinstance(route_table_id(route_table), str)
        or not route_table_id(route_table)
        or not isinstance(route_table.get("State"), str)
    ):
        module.fail_json(changed=changed, msg="EC2 returned an invalid transit gateway route table")

    return route_table


def validated_routes(module, routes, changed=False):
    if not isinstance(routes, list):
        module.fail_json(changed=changed, msg="EC2 returned invalid transit gateway routes")

    for route in routes:
        attachments = route.get("TransitGatewayAttachments") if isinstance(route, dict) else None
        if (
            not isinstance(route, dict)
            or not isinstance(route.get("State"), str)
            or not isinstance(route.get("Type"), str)
            or (attachments is not None and not isinstance(attachments, list))
            or (isinstance(attachments, list) and any(not isinstance(attachment, dict) for attachment in attachments))
        ):
            module.fail_json(changed=changed, msg="EC2 returned invalid transit gateway routes")

    return routes


def normalize_route_table(route_table):
    return boto3_resource_to_ansible_dict(route_table or {}, transform_tags=True, force_tags=False)


def normalize_routes(routes):
    return boto3_resource_list_to_ansible_dict(routes or [], transform_tags=False, force_tags=False)


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


def get_route_table_by_id(client, module, transit_gateway_route_table_id, changed=False):
    """Describe a route table; changed reports earlier modifications, for failure results."""
    if not transit_gateway_route_table_id:
        return None

    try:
        response = paginated_query_with_retries(
            client,
            "describe_transit_gateway_route_tables",
            TransitGatewayRouteTableIds=[transit_gateway_route_table_id],
        )
    except is_boto3_error_code("InvalidRouteTableID.NotFound"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            changed=changed,
            msg=f"Unable to describe EC2 transit gateway route table {transit_gateway_route_table_id}",
        )

    route_tables = response.get("TransitGatewayRouteTables") if isinstance(response, dict) else None
    if not isinstance(route_tables, list) or len(route_tables) > 1:
        module.fail_json(changed=changed, msg="EC2 returned invalid transit gateway route tables")

    if route_tables:
        return validated_route_table(module, route_tables[0], changed=changed)

    return None


def find_route_table(client, module):
    transit_gateway_route_table_id = module.params["transit_gateway_route_table_id"]
    transit_gateway_id = module.params["transit_gateway_id"]
    name = module.params["name"]

    if transit_gateway_route_table_id:
        route_table = get_route_table_by_id(client, module, transit_gateway_route_table_id)
        if route_table and transit_gateway_id and route_table.get("TransitGatewayId") != transit_gateway_id:
            module.fail_json(
                msg=(
                    f"EC2 transit gateway route table {transit_gateway_route_table_id} belongs to transit gateway "
                    f"{route_table.get('TransitGatewayId')}, not {transit_gateway_id}"
                ),
                transit_gateway_route_table_id=transit_gateway_route_table_id,
            )

        return route_table

    filters = {"state": ["available", "pending"]}
    if transit_gateway_id:
        filters["transit-gateway-id"] = transit_gateway_id

    if name:
        filters["tag:Name"] = name

    route_tables = query_list(
        module,
        client,
        "describe_transit_gateway_route_tables",
        "TransitGatewayRouteTables",
        "Unable to describe EC2 transit gateway route tables",
        Filters=ansible_dict_to_boto3_filter_list(filters),
    )

    for route_table in route_tables:
        validated_route_table(module, route_table)

    if len(route_tables) > 1:
        transit_gateway_route_table_ids = [route_table_id(route_table) for route_table in route_tables]

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
    changed=False,
):
    """Wait for a route table state; changed reports earlier modifications, for failure results."""
    deadline = time.monotonic() + module.params["wait_timeout"]
    route_table = {}
    seen = False
    target = " or ".join(sorted(desired_states))

    while time.monotonic() < deadline:
        route_table = get_route_table_by_id(client, module, transit_gateway_route_table_id, changed=changed)

        if route_table is None and absent_is_success:
            return None

        state = (route_table or {}).get("State")

        if state in desired_states:
            return route_table

        # A deleting or deleted route table cannot become available. A route table that is not yet
        # visible is retried, since EC2 describe calls are eventually consistent after a create.
        if (route_table is None and seen) or (
            state in ROUTE_TABLE_DELETED_STATES and not desired_states & ROUTE_TABLE_DELETED_STATES
        ):
            module.fail_json(
                changed=changed,
                msg=f"Unable to wait for EC2 transit gateway route table {transit_gateway_route_table_id} to become {target}",
                state=state,
                transit_gateway_route_table=normalize_route_table(route_table),
                transit_gateway_route_table_id=transit_gateway_route_table_id,
            )

        seen = seen or route_table is not None
        time.sleep(
            min(
                module.params["wait_delay"],
                max(0, deadline - time.monotonic()),
            )
        )

    module.fail_json(
        changed=changed,
        msg=f"Timed out waiting for EC2 transit gateway route table {transit_gateway_route_table_id} to become {target}",
        state=(route_table or {}).get("State"),
        transit_gateway_route_table=normalize_route_table(route_table),
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def search_routes(client, module, transit_gateway_route_table_id, filters, changed=False):
    """Search routes; changed reports earlier modifications, for failure results."""
    require_client_methods(
        module,
        client,
        "EC2",
        {
            "search_transit_gateway_routes": (
                "Filters",
                "MaxResults",
                "NextToken",
                "TransitGatewayRouteTableId",
            )
        },
        changed=changed,
    )
    routes = query_list(
        module,
        client,
        "search_transit_gateway_routes",
        "Routes",
        f"Unable to search EC2 transit gateway routes in route table {transit_gateway_route_table_id}",
        changed=changed,
        TransitGatewayRouteTableId=transit_gateway_route_table_id,
        Filters=ansible_dict_to_boto3_filter_list(filters),
        MaxResults=1000,
    )
    return validated_routes(module, routes, changed=changed)


def get_route(client, module, transit_gateway_route_table_id, destination_cidr_block, changed=False):
    routes = search_routes(
        client,
        module,
        transit_gateway_route_table_id,
        {"route-search.exact-match": destination_cidr_block},
        changed=changed,
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


def static_routes(client, module, transit_gateway_route_table_id, changed=False):
    return sorted(
        search_routes(
            client,
            module,
            transit_gateway_route_table_id,
            {"type": "static"},
            changed=changed,
        ),
        key=lambda route: route_destination(route) or "",
    )


def desired_route_matches(route, desired):
    if route is None:
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
    return route is not None and route.get("State") not in ROUTE_DELETED_STATES


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


def wait_for_route(client, module, transit_gateway_route_table_id, desired, changed=False):
    """Wait for a route; changed reports earlier modifications, for failure results."""
    deadline = time.monotonic() + module.params["wait_timeout"]
    route = {}
    seen = False
    target = "blackhole" if desired.get("blackhole") else "active"

    while time.monotonic() < deadline:
        route = get_route(
            client,
            module,
            transit_gateway_route_table_id,
            desired["destination_cidr_block"],
            changed=changed,
        )

        if desired_route_matches(route, desired) and route.get("State") in (
            "active",
            "blackhole",
        ):
            return route

        # A deleting or deleted route cannot become active or blackhole. A route that is not yet
        # visible is retried, since route searches are eventually consistent after a create.
        if (route is None and seen) or (route or {}).get("State") in ROUTE_DELETED_STATES:
            module.fail_json(
                changed=changed,
                msg=f"Unable to wait for EC2 transit gateway route {desired['destination_cidr_block']} to become {target}",
                route=normalize_routes([route])[0] if route else {},
                transit_gateway_route_table_id=transit_gateway_route_table_id,
            )

        seen = seen or route is not None
        time.sleep(
            min(
                module.params["wait_delay"],
                max(0, deadline - time.monotonic()),
            )
        )

    module.fail_json(
        changed=changed,
        msg=f"Timed out waiting for EC2 transit gateway route {desired['destination_cidr_block']} to become {target}",
        route=normalize_routes([route])[0] if route else {},
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def wait_for_route_absent(client, module, transit_gateway_route_table_id, destination_cidr_block, changed=False):
    """Wait for a route to be removed; changed reports earlier modifications, for failure results."""
    deadline = time.monotonic() + module.params["wait_timeout"]
    route = {}

    while time.monotonic() < deadline:
        route = get_route(client, module, transit_gateway_route_table_id, destination_cidr_block, changed=changed)

        if route is None:
            return

        time.sleep(
            min(
                module.params["wait_delay"],
                max(0, deadline - time.monotonic()),
            )
        )

    module.fail_json(
        changed=changed,
        msg=f"Timed out waiting for EC2 transit gateway route {destination_cidr_block} to be removed",
        route=normalize_routes([route])[0] if route else {},
        transit_gateway_route_table_id=transit_gateway_route_table_id,
    )


def ensure_route_absent(client, module, transit_gateway_route_table_id, destination_cidr_block, route, changed=False):
    """Remove the static route; route is the current route as get_route() selects it, or None.

    changed reports earlier modifications, for failure results.
    """
    wait = module.params["wait"] and not module.check_mode

    if not route_is_static(route):
        if wait and route and route.get("State") == "deleting":
            route = wait_for_route_absent(
                client, module, transit_gateway_route_table_id, destination_cidr_block, changed=changed
            )

        return False, route

    if module.check_mode:
        return True, None

    require_client_methods(
        module,
        client,
        "EC2",
        {
            "delete_transit_gateway_route": (
                "DestinationCidrBlock",
                "TransitGatewayRouteTableId",
            )
        },
        changed=changed,
    )
    try:
        response = client.delete_transit_gateway_route(
            DestinationCidrBlock=destination_cidr_block,
            TransitGatewayRouteTableId=transit_gateway_route_table_id,
            aws_retry=True,
        )
    except is_boto3_error_code(["InvalidRoute.NotFound", "InvalidRouteTableID.NotFound"]):
        # The route or its table was already deleted elsewhere.
        return False, None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            changed=changed,
            msg=f"Unable to delete EC2 transit gateway route {destination_cidr_block}",
        )

    if wait:
        return True, wait_for_route_absent(
            client, module, transit_gateway_route_table_id, destination_cidr_block, changed=True
        )

    # Return the route as EC2 left it; get_route() selects no route once it is deleted.
    route = validated_routes(
        module,
        [response.get("Route") if isinstance(response, dict) else None],
        changed=True,
    )[0]
    return True, None if route.get("State") == "deleted" else route


def ensure_present(client, module):
    route_table_identifier = module.params["transit_gateway_route_table_id"]
    transit_gateway_id = module.params["transit_gateway_id"]
    manage_routes = module.params["routes"] is not None
    desired_routes = module.params["routes"] or []
    purge_routes = module.params["purge_routes"]
    wait = module.params["wait"] and not module.check_mode
    route_table = find_route_table(client, module)

    changed = False

    if route_table is None:
        if route_table_identifier:
            module.fail_json(
                msg=f"EC2 transit gateway route table {route_table_identifier} does not exist",
                transit_gateway_route_table_id=route_table_identifier,
            )

        changed = True
        if module.check_mode:
            route_table = {
                "State": "available",
                "Tags": ansible_dict_to_boto3_tag_list(desired_tags(module)),
                "TransitGatewayId": transit_gateway_id,
                "TransitGatewayRouteTableId": "",
            }
        else:
            request = {"TransitGatewayId": transit_gateway_id}
            tag_specs = boto3_tag_specifications(desired_tags(module), types="transit-gateway-route-table")
            if tag_specs is not None:
                request["TagSpecifications"] = tag_specs

            require_client_methods(
                module,
                client,
                "EC2",
                {"create_transit_gateway_route_table": tuple(request)},
            )
            try:
                response = client.create_transit_gateway_route_table(**request, aws_retry=True)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg="Unable to create EC2 transit gateway route table")

            route_table = validated_route_table(
                module,
                response.get("TransitGatewayRouteTable") if isinstance(response, dict) else None,
                changed=True,
            )

            if wait or manage_routes:
                route_table = wait_for_route_table(
                    client, module, route_table_id(route_table), {"available"}, changed=True
                )
    elif route_table.get("State") == "deleted":
        module.fail_json(
            msg=f"EC2 transit gateway route table {route_table_id(route_table)} is deleted",
            transit_gateway_route_table=normalize_route_table(route_table),
            transit_gateway_route_table_id=route_table_id(route_table),
        )
    elif route_table.get("State") == "deleting":
        module.fail_json(
            msg=f"EC2 transit gateway route table {route_table_id(route_table)} is deleting",
            transit_gateway_route_table=normalize_route_table(route_table),
            transit_gateway_route_table_id=route_table_id(route_table),
        )
    elif not module.check_mode and route_table.get("State") == "pending" and (wait or manage_routes):
        route_table = wait_for_route_table(client, module, route_table_id(route_table), {"available"})

    # Failures after the first modification report changed=True.
    mutated = changed and not module.check_mode
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
                reconcile_ec2_tags(
                    module,
                    client,
                    [route_table_id(route_table)],
                    tags_to_set,
                    tag_keys_to_unset,
                    "EC2 transit gateway route table",
                    changed=mutated,
                    check_sdk=True,
                )
                mutated = True

            route_table = apply_tag_deltas(route_table, tags_to_set, tag_keys_to_unset)

        changed = changed or tag_changed

    route_changed = False
    routes = None
    if manage_routes:
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
                        get_route(
                            client,
                            module,
                            transit_gateway_route_table_id,
                            desired_route["destination_cidr_block"],
                            changed=mutated,
                        ),
                        changed=mutated,
                    )
                else:
                    destination_cidr_block = desired_route["destination_cidr_block"]
                    current_route = get_route(
                        client,
                        module,
                        transit_gateway_route_table_id,
                        destination_cidr_block,
                        changed=mutated,
                    )
                    if current_route and current_route.get("State") == "deleting":
                        if not module.check_mode:
                            wait_for_route_absent(
                                client,
                                module,
                                transit_gateway_route_table_id,
                                destination_cidr_block,
                                changed=mutated,
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
                                changed=mutated,
                            )
                    elif module.check_mode:
                        current_route_changed = True
                        current_route = check_mode_route(desired_route)
                    else:
                        request = {
                            "DestinationCidrBlock": destination_cidr_block,
                            "TransitGatewayRouteTableId": (transit_gateway_route_table_id),
                        }
                        if desired_route.get("blackhole"):
                            request["Blackhole"] = True
                        else:
                            request["TransitGatewayAttachmentId"] = desired_route["transit_gateway_attachment_id"]

                        current_route_changed = True
                        if current_route is None:
                            require_client_methods(
                                module,
                                client,
                                "EC2",
                                {"create_transit_gateway_route": tuple(request)},
                                changed=mutated,
                            )
                            try:
                                response = client.create_transit_gateway_route(
                                    **request,
                                    aws_retry=True,
                                )
                            except (BotoCoreError, ClientError) as e:
                                module.fail_json_aws(
                                    e,
                                    changed=mutated,
                                    msg=f"Unable to create EC2 transit gateway route {destination_cidr_block}",
                                )

                        else:
                            require_client_methods(
                                module,
                                client,
                                "EC2",
                                {"replace_transit_gateway_route": tuple(request)},
                                changed=mutated,
                            )
                            try:
                                response = client.replace_transit_gateway_route(
                                    **request,
                                    aws_retry=True,
                                )
                            except (BotoCoreError, ClientError) as e:
                                module.fail_json_aws(
                                    e,
                                    changed=mutated,
                                    msg=f"Unable to replace EC2 transit gateway route {destination_cidr_block}",
                                )

                        mutated = True
                        current_route = validated_routes(
                            module,
                            [response.get("Route") if isinstance(response, dict) else None],
                            changed=True,
                        )[0]

                        if wait:
                            current_route = wait_for_route(
                                client,
                                module,
                                transit_gateway_route_table_id,
                                desired_route,
                                changed=True,
                            )

                route_changed = route_changed or current_route_changed
                mutated = mutated or (current_route_changed and not module.check_mode)
                if current_route:
                    routes.append(current_route)

            if purge_routes:
                desired_destinations = set()
                for desired_route in desired_routes:
                    if desired_route.get("state", "present") != "present":
                        continue

                    desired_destinations.add(desired_route["destination_cidr_block"])

                # Select the route for each destination as get_route() does, so purging needs no further search.
                purge_routes_by_destination = {}
                for current_route in static_routes(client, module, transit_gateway_route_table_id, changed=mutated):
                    destination = route_destination(current_route)
                    if not destination or destination in desired_destinations:
                        continue

                    if current_route.get("State") == "deleted":
                        continue

                    selected_route = purge_routes_by_destination.get(destination)
                    if selected_route is None or route_sort_key(current_route) < route_sort_key(selected_route):
                        purge_routes_by_destination[destination] = current_route

                for destination, current_route in sorted(purge_routes_by_destination.items()):
                    purged_route_changed = ensure_route_absent(
                        client,
                        module,
                        transit_gateway_route_table_id,
                        destination,
                        current_route,
                        changed=mutated,
                    )[0]
                    route_changed = route_changed or purged_route_changed
                    mutated = mutated or (purged_route_changed and not module.check_mode)

    changed = changed or route_changed

    exit_module(module, changed, route_table, routes=routes)


def ensure_absent(client, module):
    wait = module.params["wait"] and not module.check_mode
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
    if route_table.get("State") == "pending":
        route_table = wait_for_route_table(client, module, transit_gateway_route_table_id, {"available"})

    require_client_methods(
        module,
        client,
        "EC2",
        {"delete_transit_gateway_route_table": ("TransitGatewayRouteTableId",)},
    )
    try:
        response = client.delete_transit_gateway_route_table(
            TransitGatewayRouteTableId=transit_gateway_route_table_id,
            aws_retry=True,
        )
        route_table = validated_route_table(
            module,
            response.get("TransitGatewayRouteTable") if isinstance(response, dict) else None,
            changed=True,
        )
    except is_boto3_error_code("InvalidRouteTableID.NotFound"):
        # The route table was already deleted elsewhere.
        exit_module(module, False, None)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete EC2 transit gateway route table {transit_gateway_route_table_id}",
        )

    if wait:
        route_table = wait_for_route_table(
            client,
            module,
            transit_gateway_route_table_id,
            {"deleted"},
            absent_is_success=True,
            changed=True,
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
        "purge_routes": {"default": True, "type": "bool"},
        "purge_tags": {"default": True, "type": "bool"},
        "routes": {
            "elements": "dict",
            "options": {
                "blackhole": {"type": "bool"},
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
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
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

    state = module.params["state"]
    routes = module.params["routes"] if state == "present" else None
    require_positive_wait_bounds(
        module,
        always=(state == "absent" or routes is not None),
    )
    destinations = set()
    for route in routes or []:
        try:
            route["destination_cidr_block"] = str(ipaddress.ip_network(route["destination_cidr_block"]))
        except ValueError:
            module.fail_json(
                msg=f"routes[].destination_cidr_block must be a valid CIDR: {route['destination_cidr_block']}"
            )

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
                msg="routes[].blackhole and routes[].transit_gateway_attachment_id are mutually exclusive",
                destination_cidr_block=route["destination_cidr_block"],
            )

        if not route.get("blackhole") and not route.get("transit_gateway_attachment_id"):
            module.fail_json(
                msg=(
                    "routes[].transit_gateway_attachment_id is required when "
                    "routes[].state=present and routes[].blackhole is not true"
                ),
                destination_cidr_block=route["destination_cidr_block"],
            )

    if state == "present":
        tags = module.params["tags"]
        name = module.params["name"]
        require_valid_tags(module, tags, 50, key_max=127)
        if name and tags is not None and tags.get("Name", name) != name:
            module.fail_json(msg="tags.Name must match name")

        # The Name tag counts toward the EC2 tag limit.
        require_valid_tags(module, desired_tags(module), 50, key_max=127)

    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    describe_parameters = (
        ("MaxResults", "NextToken", "TransitGatewayRouteTableIds")
        if module.params.get("transit_gateway_route_table_id")
        else ("Filters", "MaxResults", "NextToken", "TransitGatewayRouteTableIds")
    )
    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_transit_gateway_route_tables": describe_parameters},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
