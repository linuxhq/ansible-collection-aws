from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_transit_gateway_route_table_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["transit_gateway_route_table_ids"]["elements"] == "str"


def test_routes_sort_by_destination_type_and_state():
    routes = [
        {"PrefixListId": "pl-2", "Type": "propagated", "State": "active"},
        {"DestinationCidrBlock": "10.0.0.0/8", "Type": "static", "State": "active"},
    ]
    assert min(routes, key=plugin.route_sort_key)["DestinationCidrBlock"] == "10.0.0.0/8"


def test_route_search_uses_paginated_query():
    client = Mock()
    module = FakeModule(
        {
            "filters": None,
            "transit_gateway_route_table_ids": ["tgw-rtb-1", "tgw-rtb-1"],
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "query_list",
            return_value=[
                {
                    "State": "available",
                    "TransitGatewayRouteTableId": "tgw-rtb-1",
                }
            ],
        ) as query,
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={
                "Routes": [
                    {"DestinationCidrBlock": "10.0.0.0/8", "State": "active", "Type": "static"},
                    {"DestinationCidrBlock": "192.0.2.0/24", "State": "active", "Type": "static"},
                ]
            },
        ) as search,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert require.call_args_list[0].args[3]["describe_transit_gateway_route_tables"] == (
        "Filters",
        "MaxResults",
        "NextToken",
    )
    assert require.call_args_list[1].args[3]["search_transit_gateway_routes"] == (
        "Filters",
        "MaxResults",
        "NextToken",
        "TransitGatewayRouteTableId",
    )
    assert len(raised.value.values["transit_gateway_route_tables"][0]["routes"]) == 2
    search.assert_called_once_with(
        client,
        "search_transit_gateway_routes",
        TransitGatewayRouteTableId="tgw-rtb-1",
        Filters=[{"Name": "type", "Values": ["static", "propagated"]}],
        MaxResults=1000,
    )
    assert query.call_args.kwargs == {"Filters": [{"Name": "transit-gateway-route-table-id", "Values": ["tgw-rtb-1"]}]}
    client.search_transit_gateway_routes.assert_not_called()


def test_empty_results_do_not_require_route_search():
    client = Mock()
    module = FakeModule(
        {"filters": None, "transit_gateway_route_table_ids": None},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_count == 1
    assert "search_transit_gateway_routes" not in require.call_args.args[3]


def test_rejects_malformed_route_table_response():
    module = FakeModule(
        {"filters": None, "transit_gateway_route_table_ids": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail),
    ):
        plugin.main()


def test_rejects_malformed_route_response():
    module = FakeModule(
        {"filters": None, "transit_gateway_route_table_ids": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}],
        ),
        patch.object(plugin, "paginated_query_with_retries", return_value={"Routes": [None]}),
        pytest.raises(ModuleFail),
    ):
        plugin.main()


def test_route_table_ids_take_precedence_over_the_id_filter():
    module = FakeModule(
        {
            "filters": {"state": "available", "transit-gateway-route-table-id": "ignored"},
            "transit_gateway_route_table_ids": ["tgw-rtb-1"],
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert sorted(query.call_args.kwargs["Filters"], key=lambda item: item["Name"]) == [
        {"Name": "state", "Values": ["available"]},
        {"Name": "transit-gateway-route-table-id", "Values": ["tgw-rtb-1"]},
    ]
    assert module.params["filters"]["transit-gateway-route-table-id"] == "ignored"


def test_missing_route_table_id_returns_an_empty_list():
    module = FakeModule(
        {"filters": None, "transit_gateway_route_table_ids": ["tgw-rtb-missing"]},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["transit_gateway_route_tables"] == []
    assert "TransitGatewayRouteTableIds" not in query.call_args.kwargs


def test_route_table_deleted_before_route_search_is_omitted():
    module = FakeModule(
        {"filters": None, "transit_gateway_route_table_ids": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[
                {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-gone"},
                {"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"},
            ],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[
                plugin.ClientError(
                    {"Error": {"Code": "InvalidRouteTableID.NotFound", "Message": "gone"}},
                    "SearchTransitGatewayRoutes",
                ),
                {"Routes": []},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [
        route_table["transit_gateway_route_table_id"]
        for route_table in raised.value.values["transit_gateway_route_tables"]
    ] == ["tgw-rtb-1"]


def test_route_search_failures_are_reported():
    module = FakeModule(
        {"filters": None, "transit_gateway_route_table_ids": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=plugin.ClientError(
                {"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}},
                "SearchTransitGatewayRoutes",
            ),
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Unable to search EC2 transit gateway routes in route table tgw-rtb-1"


def test_boolean_and_numeric_filter_list_entries_are_sent_as_strings():
    module = FakeModule(
        {
            "filters": {"default-association-route-table": [True], "x-count": [2]},
            "transit_gateway_route_table_ids": None,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_args.kwargs["Filters"] == [
        {"Name": "default-association-route-table", "Values": ["true"]},
        {"Name": "x-count", "Values": ["2"]},
    ]
