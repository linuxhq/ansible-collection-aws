from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_transit_gateway_route_table_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Ec2TransitGatewayRouteTableInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["transit_gateway_route_table_ids"]["elements"] == "str"

    def test_routes_sort_by_destination_type_and_state(self):
        routes = [
            {"PrefixListId": "pl-2", "Type": "propagated", "State": "active"},
            {"DestinationCidrBlock": "10.0.0.0/8", "Type": "static", "State": "active"},
        ]
        assert min(routes, key=plugin.route_sort_key)["DestinationCidrBlock"] == "10.0.0.0/8"

    def test_route_search_uses_paginated_query(self):
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
                side_effect=[
                    [
                        {
                            "State": "available",
                            "TransitGatewayRouteTableId": "tgw-rtb-1",
                        }
                    ],
                    [
                        {"DestinationCidrBlock": "10.0.0.0/8", "State": "active", "Type": "static"},
                        {"DestinationCidrBlock": "192.0.2.0/24", "State": "active", "Type": "static"},
                    ],
                ],
            ) as query,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(
            require.call_args_list[0].args[3]["describe_transit_gateway_route_tables"],
            ("TransitGatewayRouteTableIds", "MaxResults", "NextToken"),
        )
        self.assertEqual(
            require.call_args_list[1].args[3]["search_transit_gateway_routes"],
            ("Filters", "MaxResults", "NextToken", "TransitGatewayRouteTableId"),
        )
        self.assertEqual(
            len(raised.exception.values["transit_gateway_route_tables"][0]["routes"]),
            2,
        )
        self.assertEqual(query.call_args_list[1].args[2], "search_transit_gateway_routes")
        self.assertEqual(
            query.call_args_list[0].kwargs["TransitGatewayRouteTableIds"],
            ["tgw-rtb-1"],
        )
        client.search_transit_gateway_routes.assert_not_called()

    def test_empty_results_do_not_require_route_search(self):
        client = Mock()
        module = FakeModule(
            {"filters": None, "transit_gateway_route_table_ids": None},
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(require.call_count, 1)
        self.assertNotIn("search_transit_gateway_routes", require.call_args.args[3])

    def test_rejects_malformed_route_table_response(self):
        module = FakeModule(
            {"filters": None, "transit_gateway_route_table_ids": None},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[None]),
            self.assertRaises(ModuleFail),
        ):
            plugin.main()

    def test_rejects_malformed_route_response(self):
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
                side_effect=[
                    [{"State": "available", "TransitGatewayRouteTableId": "tgw-rtb-1"}],
                    [None],
                ],
            ),
            self.assertRaises(ModuleFail),
        ):
            plugin.main()
