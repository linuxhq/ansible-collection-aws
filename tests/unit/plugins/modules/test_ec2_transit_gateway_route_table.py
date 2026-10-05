from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

import pytest
import yaml

from ansible_collections.linuxhq.aws.plugins.modules import ec2_transit_gateway_route_table as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


def test_route_delete_tolerates_route_disappearing():
    client = Mock()
    client.delete_transit_gateway_route.side_effect = plugin.ClientError(
        {"Error": {"Code": "InvalidRoute.NotFound", "Message": "gone"}},
        "DeleteTransitGatewayRoute",
    )
    module = FakeModule({"wait": True})
    with (
        patch.object(plugin, "wait_for_route_absent") as wait,
        patch.object(plugin, "require_client_methods"),
    ):
        changed, route = plugin.ensure_route_absent(
            client, module, "tgw-rtb-1", "10.0.0.0/8", {"State": "active", "Type": "static"}
        )

    assert changed
    assert route is None
    wait.assert_not_called()


def test_absent_tolerates_route_table_disappearing_during_delete():
    client = Mock()
    client.delete_transit_gateway_route_table.side_effect = plugin.ClientError(
        {
            "Error": {
                "Code": "InvalidRouteTableID.NotFound",
                "Message": "gone",
            }
        },
        "DeleteTransitGatewayRouteTable",
    )
    module = FakeModule({"state": "absent", "wait": False})
    current = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    with (
        patch.object(plugin, "find_route_table", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]


def test_module_contract():
    options = assert_module_contract(plugin)
    assert len(options["required_one_of"]) == 2
    assert "default" not in options["argument_spec"]["routes"]["options"]["blackhole"]
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]
    assert options["argument_spec"]["purge_routes"]["default"] is True


def test_name_is_merged_into_desired_tags():
    module = SimpleNamespace(params={"name": "main", "tags": {"Env": "prod"}})
    assert plugin.desired_tags(module) == {"Env": "prod", "Name": "main"}


def test_name_tag_counts_toward_provider_limit():
    module = FakeModule(
        {
            "name": "main",
            "purge_routes": False,
            "routes": None,
            "state": "present",
            "tags": {str(index): "" for index in range(50)},
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "tags must contain at most 50 entries"


def test_absent_does_not_validate_unused_routes():
    module = FakeModule(
        {
            "purge_routes": True,
            "routes": [{"destination_cidr_block": "not-a-cidr"}],
            "state": "absent",
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "ensure_absent") as ensure_absent,
    ):
        plugin.main()

    ensure_absent.assert_called_once_with(None, module)


def test_create_without_tags_does_not_gate_tag_specifications():
    client = Mock()
    module = FakeModule(
        {
            "name": None,
            "purge_routes": False,
            "purge_tags": True,
            "routes": None,
            "state": "present",
            "tags": None,
            "transit_gateway_id": "tgw-1",
            "transit_gateway_route_table_id": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    require_methods.assert_called_once_with(
        module,
        client,
        "EC2",
        {
            "describe_transit_gateway_route_tables": (
                "Filters",
                "MaxResults",
                "NextToken",
                "TransitGatewayRouteTableIds",
            )
        },
    )


def test_name_only_create_does_not_gate_separate_tag_api():
    client = Mock()
    module = FakeModule(
        {
            "name": "main",
            "purge_routes": False,
            "purge_tags": True,
            "routes": None,
            "state": "present",
            "tags": None,
            "transit_gateway_id": "tgw-1",
            "transit_gateway_route_table_id": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    assert require_methods.call_args.args[3] == {
        "describe_transit_gateway_route_tables": (
            "Filters",
            "MaxResults",
            "NextToken",
            "TransitGatewayRouteTableIds",
        )
    }


def test_static_route_matches_attachment():
    route = {
        "State": "active",
        "Type": "static",
        "TransitGatewayAttachments": [{"TransitGatewayAttachmentId": "tgw-attach-1"}],
    }
    assert plugin.desired_route_matches(route, {"transit_gateway_attachment_id": "tgw-attach-1"})
    assert not plugin.desired_route_matches(route, {"transit_gateway_attachment_id": "tgw-attach-2"})


def test_check_mode_builds_blackhole_route():
    assert plugin.check_mode_route({"blackhole": True, "destination_cidr_block": "10.0.0.0/8"}) == {
        "DestinationCidrBlock": "10.0.0.0/8",
        "State": "blackhole",
        "TransitGatewayAttachments": [],
        "Type": "static",
    }


def test_propagated_route_is_not_deleted():
    client = Mock()
    module = SimpleNamespace(params={"wait": False}, check_mode=False)
    route = {"State": "active", "Type": "propagated"}
    changed, returned = plugin.ensure_route_absent(client, module, "tgw-rtb-1", "10.0.0.0/8", route)

    assert not changed
    assert returned is route
    client.delete_transit_gateway_route.assert_not_called()


def test_changed_static_route_is_replaced_in_place():
    client = Mock()
    replacement = {
        "DestinationCidrBlock": "10.0.0.0/8",
        "State": "active",
        "TransitGatewayAttachments": [{"TransitGatewayAttachmentId": "tgw-attach-new"}],
        "Type": "static",
    }
    client.replace_transit_gateway_route.return_value = {"Route": replacement}
    module = FakeModule(
        {
            "name": None,
            "purge_routes": False,
            "purge_tags": True,
            "routes": [
                {
                    "destination_cidr_block": "10.0.0.0/8",
                    "transit_gateway_attachment_id": "tgw-attach-new",
                }
            ],
            "state": "present",
            "tags": None,
            "transit_gateway_id": None,
            "transit_gateway_route_table_id": "tgw-rtb-1",
            "wait": False,
        }
    )
    route_table = {
        "State": "available",
        "TransitGatewayRouteTableId": "tgw-rtb-1",
    }
    current_route = dict(
        replacement,
        TransitGatewayAttachments=[{"TransitGatewayAttachmentId": "tgw-attach-old"}],
    )
    with (
        patch.object(plugin, "find_route_table", return_value=route_table),
        patch.object(plugin, "get_route", return_value=current_route),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    client.replace_transit_gateway_route.assert_called_once_with(
        DestinationCidrBlock="10.0.0.0/8",
        TransitGatewayAttachmentId="tgw-attach-new",
        TransitGatewayRouteTableId="tgw-rtb-1",
        aws_retry=True,
    )
    client.create_transit_gateway_route.assert_not_called()


def test_new_table_waits_before_routes_when_final_wait_is_disabled():
    client = Mock()
    client.create_transit_gateway_route_table.return_value = {
        "TransitGatewayRouteTable": {
            "State": "pending",
            "TransitGatewayRouteTableId": "tgw-rtb-1",
        }
    }
    route = {
        "DestinationCidrBlock": "10.0.0.0/8",
        "State": "blackhole",
        "TransitGatewayAttachments": [],
        "Type": "static",
    }
    module = FakeModule(
        {
            "name": None,
            "purge_routes": False,
            "purge_tags": True,
            "routes": [
                {
                    "blackhole": True,
                    "destination_cidr_block": "10.0.0.0/8",
                }
            ],
            "state": "present",
            "tags": None,
            "transit_gateway_id": "tgw-1",
            "transit_gateway_route_table_id": None,
            "wait": False,
        }
    )
    available = {
        "State": "available",
        "TransitGatewayRouteTableId": "tgw-rtb-1",
    }
    with (
        patch.object(plugin, "find_route_table", return_value=None),
        patch.object(plugin, "wait_for_route_table", return_value=available) as wait,
        patch.object(plugin, "get_route", return_value=route),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait.assert_called_once_with(client, module, "tgw-rtb-1", {"available"}, changed=True)


def test_absent_waits_for_pending_table_when_final_wait_is_disabled():
    client = Mock(
        delete_transit_gateway_route_table=Mock(
            return_value={
                "TransitGatewayRouteTable": {
                    "State": "deleting",
                    "TransitGatewayRouteTableId": "tgw-rtb-1",
                }
            }
        )
    )
    module = FakeModule({"state": "absent", "wait": False})
    pending = {
        "State": "pending",
        "TransitGatewayRouteTableId": "tgw-rtb-1",
    }
    available = dict(pending, State="available")
    with (
        patch.object(plugin, "find_route_table", return_value=pending),
        patch.object(plugin, "wait_for_route_table", return_value=available) as wait_for_route_table,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_absent(client, module)

    wait_for_route_table.assert_called_once_with(client, module, "tgw-rtb-1", {"available"})
    client.delete_transit_gateway_route_table.assert_called_once_with(
        TransitGatewayRouteTableId="tgw-rtb-1", aws_retry=True
    )


def test_deleting_route_waits_before_recreation_when_final_wait_is_disabled():
    client = Mock()
    client.create_transit_gateway_route.return_value = {
        "Route": {
            "DestinationCidrBlock": "10.0.0.0/8",
            "State": "blackhole",
            "Type": "static",
        }
    }
    module = FakeModule(
        {
            "name": None,
            "purge_routes": False,
            "purge_tags": True,
            "routes": [
                {
                    "blackhole": True,
                    "destination_cidr_block": "10.0.0.0/8",
                }
            ],
            "state": "present",
            "tags": None,
            "transit_gateway_id": None,
            "transit_gateway_route_table_id": "tgw-rtb-1",
            "wait": False,
        }
    )
    route_table = {
        "State": "available",
        "TransitGatewayRouteTableId": "tgw-rtb-1",
    }
    deleting = {
        "DestinationCidrBlock": "10.0.0.0/8",
        "State": "deleting",
        "Type": "static",
    }
    with (
        patch.object(plugin, "find_route_table", return_value=route_table),
        patch.object(plugin, "get_route", return_value=deleting),
        patch.object(plugin, "wait_for_route_absent", return_value=None) as wait,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait.assert_called_once_with(client, module, "tgw-rtb-1", "10.0.0.0/8", changed=False)
    client.create_transit_gateway_route.assert_called_once()


def test_routes_require_unique_destinations_and_a_target():
    base = {"purge_routes": False, "state": "present"}
    cases = [
        (
            dict(
                base,
                routes=[
                    {
                        "blackhole": True,
                        "destination_cidr_block": "not-a-cidr",
                    }
                ],
            ),
            "routes[].destination_cidr_block must be a valid CIDR: not-a-cidr",
        ),
        (
            dict(
                base,
                routes=[
                    {
                        "blackhole": True,
                        "destination_cidr_block": "10.0.0.0/8",
                    },
                    {
                        "blackhole": True,
                        "destination_cidr_block": "10.0.0.0/8",
                    },
                ],
            ),
            "routes[].destination_cidr_block values must be unique",
        ),
        (
            dict(
                base,
                routes=[
                    {
                        "blackhole": False,
                        "destination_cidr_block": "10.0.0.0/8",
                    }
                ],
            ),
            "routes[].transit_gateway_attachment_id is required when routes[].state=present and routes[].blackhole is not true",
        ),
        (
            dict(
                base,
                routes=[
                    {
                        "blackhole": True,
                        "destination_cidr_block": "10.0.0.0/8",
                        "transit_gateway_attachment_id": "tgw-attach-1",
                    }
                ],
            ),
            "routes[].blackhole and routes[].transit_gateway_attachment_id are mutually exclusive",
        ),
    ]
    for params, message in cases:
        assert_module_rejects(plugin, params, message)


def test_false_blackhole_allows_attachment():
    module = FakeModule(
        {
            "name": None,
            "purge_routes": False,
            "routes": [
                {
                    "blackhole": False,
                    "destination_cidr_block": "10.0.0.0/8",
                    "transit_gateway_attachment_id": "tgw-attach-1",
                }
            ],
            "state": "present",
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_valid_tags"),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


def test_route_search_uses_all_paginated_results():
    client = Mock()
    routes = [{"DestinationCidrBlock": "10.0.0.0/8", "State": "active", "Type": "static"}]
    with (
        patch.object(plugin, "query_list", return_value=routes) as query,
        patch.object(plugin, "require_client_methods"),
    ):
        result = plugin.search_routes(
            client,
            FakeModule({}),
            "tgw-rtb-1",
            {"type": ["static"]},
        )

    assert result == routes
    assert query.call_args.args[2:4] == ("search_transit_gateway_routes", "Routes")
    assert query.call_args.kwargs["TransitGatewayRouteTableId"] == "tgw-rtb-1"
    client.search_transit_gateway_routes.assert_not_called()


def test_route_table_lookup_rejects_malformed_response():
    with (
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"TransitGatewayRouteTables": [{}]},
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_route_table_by_id(Mock(), FakeModule({}), "tgw-rtb-1")

    assert "invalid transit gateway route table" in raised.value.values["msg"]


def test_route_search_rejects_malformed_response():
    with (
        patch.object(plugin, "query_list", return_value=[None]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.search_routes(Mock(), FakeModule({}), "tgw-rtb-1", {"type": ["static"]})

    assert "invalid transit gateway routes" in raised.value.values["msg"]


def test_purge_removes_only_undesired_static_routes():
    client = Mock()
    desired_route = {
        "DestinationCidrBlock": "10.0.0.0/8",
        "State": "active",
        "TransitGatewayAttachments": [{"TransitGatewayAttachmentId": "tgw-attach-1"}],
        "Type": "static",
    }
    stale_route = dict(desired_route, DestinationCidrBlock="192.0.2.0/24")
    module = FakeModule(
        {
            "name": None,
            "purge_routes": True,
            "purge_tags": True,
            "routes": [
                {
                    "destination_cidr_block": "10.0.0.0/8",
                    "transit_gateway_attachment_id": "tgw-attach-1",
                }
            ],
            "state": "present",
            "tags": None,
            "transit_gateway_id": None,
            "transit_gateway_route_table_id": "tgw-rtb-1",
            "wait": False,
        }
    )
    route_table = {
        "State": "available",
        "TransitGatewayRouteTableId": "tgw-rtb-1",
    }
    with (
        patch.object(plugin, "find_route_table", return_value=route_table),
        patch.object(plugin, "get_route", return_value=desired_route),
        patch.object(plugin, "static_routes", return_value=[desired_route, stale_route]) as static_routes,
        patch.object(plugin, "ensure_route_absent", return_value=(True, None)) as remove,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    remove.assert_called_once_with(client, module, "tgw-rtb-1", "192.0.2.0/24", stale_route, changed=False)
    static_routes.assert_called_once()
    assert [route["destination_cidr_block"] for route in raised.value.values["routes"]] == ["10.0.0.0/8"]


def test_tgw_absence_waits_until_deleting_route_disappears():
    route = {"Type": "static", "State": "deleting", "DestinationCidrBlock": "10.0.0.0/24"}
    with patch.object(plugin, "get_route", side_effect=[route, None]) as get, patch.object(plugin.time, "sleep"):
        result = plugin.wait_for_route_absent(
            Mock(), FakeModule({"wait_timeout": 10, "wait_delay": 1}), "tgw-rtb-1", "10.0.0.0/24"
        )

    assert result is None
    assert get.call_count == 2


@pytest.mark.parametrize("case", ["pending_table", "pending_route", "deleting_route", "purge_pending_table"])
def test_present_check_mode_skips_transition_waits(case):
    desired = {"destination_cidr_block": "10.0.0.0/8", "transit_gateway_attachment_id": "tgw-attach-1"}
    module = FakeModule(
        {
            "state": "present",
            "transit_gateway_route_table_id": "tgw-rtb-1",
            "transit_gateway_id": None,
            "name": None,
            "tags": None,
            "purge_tags": True,
            "routes": [desired] if case in ("pending_route", "deleting_route") else [],
            "purge_routes": case == "purge_pending_table",
            "wait": case != "purge_pending_table",
        },
        check_mode=True,
    )
    table = {"TransitGatewayRouteTableId": "tgw-rtb-1", "State": "pending" if "table" in case else "available"}
    route = {
        "Type": "static",
        "State": "deleting" if case == "deleting_route" else "pending",
        "DestinationCidrBlock": "10.0.0.0/8",
        "TransitGatewayAttachments": [{"TransitGatewayAttachmentId": "tgw-attach-1"}],
    }
    client = Mock()
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "get_route", return_value=route),
        patch.object(plugin, "static_routes", return_value=[]),
        patch.object(plugin, "wait_for_route_table", side_effect=AssertionError("Unexpected table wait")),
        patch.object(plugin, "wait_for_route", side_effect=AssertionError("Unexpected route wait")),
        patch.object(plugin, "wait_for_route_absent", side_effect=AssertionError("Unexpected deletion wait")),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is (case == "deleting_route")
    if case == "deleting_route":
        assert result.value.values["routes"][0]["state"] == "active"

    assert client.mock_calls == []


def test_absent_check_mode_skips_deleting_table_wait():
    module = FakeModule({"state": "absent", "wait": True}, check_mode=True)
    table = {"TransitGatewayRouteTableId": "tgw-rtb-1", "State": "deleting"}
    client = Mock()
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "wait_for_route_table", side_effect=AssertionError("Unexpected table wait")),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_absent(client, module)

    assert result.value.values["changed"] is False
    assert client.mock_calls == []


def test_absent_check_mode_skips_deleting_route_wait():
    module = FakeModule({"wait": True}, check_mode=True)
    client = Mock()
    with patch.object(plugin, "wait_for_route_absent", side_effect=AssertionError("Unexpected route wait")):
        changed, _route = plugin.ensure_route_absent(
            client, module, "tgw-rtb-1", "10.0.0.0/8", {"Type": "static", "State": "deleting"}
        )

    assert changed is False
    assert client.mock_calls == []


def present_params(**overrides):
    return dict(
        {
            "name": None,
            "purge_routes": True,
            "purge_tags": True,
            "routes": None,
            "state": "present",
            "tags": None,
            "transit_gateway_id": None,
            "transit_gateway_route_table_id": "tgw-rtb-1",
            "wait": False,
        },
        **overrides,
    )


def test_purge_routes_is_ignored_without_routes():
    module = FakeModule(present_params())
    table = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "static_routes", side_effect=AssertionError("Unexpected route search")),
        patch.object(plugin, "get_route", side_effect=AssertionError("Unexpected route search")),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(Mock(), module)

    assert result.value.values["changed"] is False
    assert "routes" not in result.value.values


def test_empty_routes_purge_every_static_route():
    module = FakeModule(present_params(routes=[]))
    table = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    stale = {"DestinationCidrBlock": "192.0.2.0/24", "State": "active", "Type": "static"}
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "static_routes", return_value=[stale]),
        patch.object(plugin, "ensure_route_absent", return_value=(True, None)) as remove,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(Mock(), module)

    assert result.value.values["changed"] is True
    assert result.value.values["routes"] == []
    remove.assert_called_once_with(ANY, module, "tgw-rtb-1", "192.0.2.0/24", stale, changed=False)


def test_route_table_id_must_belong_to_transit_gateway():
    module = FakeModule(present_params(name="main", transit_gateway_id="tgw-1"))
    table = {"State": "available", "TransitGatewayId": "tgw-2", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    with (
        patch.object(plugin, "get_route_table_by_id", return_value=table),
        pytest.raises(ModuleFail) as result,
    ):
        plugin.find_route_table(Mock(), module)

    assert result.value.values["msg"] == (
        "EC2 transit gateway route table tgw-rtb-1 belongs to transit gateway tgw-2, not tgw-1"
    )


def test_route_table_id_matching_transit_gateway_is_returned():
    module = FakeModule(present_params(transit_gateway_id="tgw-1"))
    table = {"State": "available", "TransitGatewayId": "tgw-1", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    with patch.object(plugin, "get_route_table_by_id", return_value=table):
        assert plugin.find_route_table(Mock(), module) is table


def test_absent_route_example_disables_purge():
    examples = yaml.safe_load(plugin.EXAMPLES)
    task = next(task for task in examples if task["name"] == "Ensure a static route is absent")
    params = task["linuxhq.aws.ec2_transit_gateway_route_table"]

    assert params["purge_routes"] is False
    assert all(route["state"] == "absent" for route in params["routes"])


@pytest.mark.parametrize(
    ("purge_routes", "removed"),
    [
        (False, ["10.10.0.0/16"]),
        (True, ["10.10.0.0/16", "192.0.2.0/24"]),
    ],
)
def test_absent_only_routes_purge_other_static_routes_only_when_purging(purge_routes, removed):
    module = FakeModule(
        present_params(
            purge_routes=purge_routes,
            routes=[{"destination_cidr_block": "10.10.0.0/16", "state": "absent"}],
        )
    )
    table = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    other = {"DestinationCidrBlock": "192.0.2.0/24", "State": "active", "Type": "static"}
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "get_route", return_value=None),
        patch.object(plugin, "static_routes", return_value=[other]),
        patch.object(plugin, "ensure_route_absent", return_value=(True, None)) as remove,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(Mock(), module)

    assert result.value.values["changed"] is True
    assert [call.args[3] for call in remove.call_args_list] == removed


def test_missing_route_is_created():
    client = Mock()
    client.create_transit_gateway_route.return_value = {
        "Route": {"DestinationCidrBlock": "10.0.0.0/8", "State": "blackhole", "Type": "static"}
    }
    module = FakeModule(
        present_params(
            purge_routes=False,
            routes=[{"blackhole": True, "destination_cidr_block": "10.0.0.0/8"}],
        )
    )
    table = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "get_route", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    client.create_transit_gateway_route.assert_called_once_with(
        DestinationCidrBlock="10.0.0.0/8",
        TransitGatewayRouteTableId="tgw-rtb-1",
        Blackhole=True,
        aws_retry=True,
    )
    client.replace_transit_gateway_route.assert_not_called()


def test_purge_passes_each_found_route_without_searching_again():
    client = Mock()
    module = FakeModule(present_params(routes=[]))
    table = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    deleting = {"DestinationCidrBlock": "192.0.2.0/24", "State": "deleting", "Type": "static"}
    active = dict(deleting, State="active")
    deleted = {"DestinationCidrBlock": "198.51.100.0/24", "State": "deleted", "Type": "static"}
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "static_routes", return_value=[deleting, active, deleted]),
        patch.object(plugin, "get_route", side_effect=AssertionError("Unexpected route search")),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    client.delete_transit_gateway_route.assert_called_once_with(
        DestinationCidrBlock="192.0.2.0/24",
        TransitGatewayRouteTableId="tgw-rtb-1",
        aws_retry=True,
    )


def test_integer_tag_keys_are_normalized_before_comparison():
    client = Mock()
    module = FakeModule(present_params(name="main", tags={1: 2}), client=client)
    table = {
        "State": "available",
        "Tags": [{"Key": "1", "Value": "2"}, {"Key": "Name", "Value": "main"}],
        "TransitGatewayRouteTableId": "tgw-rtb-1",
    }
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "find_route_table", return_value=table),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    assert module.params["tags"] == {"1": "2"}
    assert result.value.values["changed"] is False
    client.create_tags.assert_not_called()
    client.delete_tags.assert_not_called()


def test_name_tag_must_match_name():
    module = FakeModule(present_params(name="main", tags={"Name": "other"}))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(module, "client", side_effect=AssertionError("Unexpected client")),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "tags.Name must match name"


@pytest.mark.parametrize(
    ("tags_to_set", "tag_keys_to_unset", "methods"),
    [
        ({"Env": "prod"}, [], {"create_tags"}),
        ({}, ["Old"], {"delete_tags"}),
        ({"Env": "prod"}, ["Old"], {"create_tags", "delete_tags"}),
    ],
)
def test_tag_changes_are_gated_and_reconciled_once(tags_to_set, tag_keys_to_unset, methods):
    client = Mock()
    module = FakeModule({})
    with (
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "reconcile_ec2_tags") as reconcile,
    ):
        plugin.reconcile_tags(client, module, "tgw-rtb-1", tags_to_set, tag_keys_to_unset)

    require.assert_called_once()
    assert set(require.call_args.args[3]) == methods
    reconcile.assert_called_once_with(
        module, client, ["tgw-rtb-1"], tags_to_set, tag_keys_to_unset, "EC2 transit gateway route table", changed=False
    )


def test_route_table_wait_timeout_names_target_state():
    module = FakeModule({"wait_delay": 1, "wait_timeout": 1})
    with (
        patch.object(plugin, "get_route_table_by_id", return_value={"State": "deleting"}),
        patch.object(plugin.time, "monotonic", side_effect=[0, 0, 0, 2]),
        patch.object(plugin.time, "sleep"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_route_table(Mock(), module, "tgw-rtb-1", {"deleted"}, absent_is_success=True)

    assert (
        raised.value.values["msg"]
        == "Timed out waiting for EC2 transit gateway route table tgw-rtb-1 to become deleted"
    )


def client_error(operation):
    return plugin.ClientError({"Error": {"Code": "InternalError", "Message": "failed"}}, operation)


@pytest.mark.parametrize(("tags", "changed"), [({"Env": "test"}, True), (None, False)])
def test_route_failure_reports_whether_tags_were_changed(tags, changed):
    client = Mock()
    client.create_transit_gateway_route.side_effect = client_error("CreateTransitGatewayRoute")
    module = FakeModule(
        present_params(
            purge_routes=False,
            routes=[{"blackhole": True, "destination_cidr_block": "10.0.0.0/8"}],
            tags=tags,
        )
    )
    table = {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    with (
        patch.object(plugin, "find_route_table", return_value=table),
        patch.object(plugin, "get_route", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Unable to create EC2 transit gateway route 10.0.0.0/8"
    assert raised.value.values["changed"] is changed
    assert client.create_tags.called is changed


def test_wait_timeout_after_create_reports_changed():
    client = Mock()
    client.create_transit_gateway_route_table.return_value = {
        "TransitGatewayRouteTable": {"State": "pending", "TransitGatewayRouteTableId": "tgw-rtb-1"}
    }
    module = FakeModule(
        dict(
            present_params(transit_gateway_id="tgw-1", transit_gateway_route_table_id=None, wait=True),
            wait_delay=1,
            wait_timeout=1,
        )
    )
    with (
        patch.object(plugin, "find_route_table", return_value=None),
        patch.object(
            plugin,
            "get_route_table_by_id",
            return_value={"State": "pending", "TransitGatewayRouteTableId": "tgw-rtb-1"},
        ),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin.time, "sleep"),
        patch.object(plugin.time, "monotonic", side_effect=[0, 0, 0, 2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"].startswith("Timed out waiting for EC2 transit gateway route table tgw-rtb-1")


@pytest.mark.parametrize("changed", [True, False])
def test_route_wait_timeout_reports_earlier_changes(changed):
    module = FakeModule({"wait_delay": 1, "wait_timeout": 1})
    desired = {"blackhole": True, "destination_cidr_block": "10.0.0.0/8"}
    with (
        patch.object(plugin, "get_route", return_value=None),
        patch.object(plugin.time, "sleep"),
        patch.object(plugin.time, "monotonic", side_effect=[0, 0, 0, 2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_route(Mock(), module, "tgw-rtb-1", desired, changed=changed)

    assert raised.value.values["changed"] is changed
