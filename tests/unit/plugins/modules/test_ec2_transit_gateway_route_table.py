from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_transit_gateway_route_table as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class Ec2TransitGatewayRouteTableTests(TestCase):
    def test_route_delete_tolerates_route_disappearing(self):
        client = Mock()
        client.delete_transit_gateway_route.side_effect = plugin.ClientError(
            {"Error": {"Code": "InvalidRoute.NotFound", "Message": "gone"}},
            "DeleteTransitGatewayRoute",
        )
        module = FakeModule({"wait": True})
        with (
            patch.object(
                plugin,
                "get_route",
                return_value={"State": "active", "Type": "static"},
            ),
            patch.object(plugin, "wait_for_route_absent") as wait,
            patch.object(plugin, "require_client_methods"),
        ):
            changed, route = plugin.ensure_route_absent(client, module, "tgw-rtb-1", "10.0.0.0/8")
        self.assertTrue(changed)
        self.assertIsNone(route)
        wait.assert_not_called()

    def test_absent_tolerates_route_table_disappearing_during_delete(self):
        client = Mock()
        client.delete_transit_gateway_route_table.side_effect = plugin.ClientError(
            {
                "Error": {
                    "Code": "InvalidTransitGatewayRouteTableID.NotFound",
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
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert len(options["required_one_of"]) == 2
        assert "default" not in options["argument_spec"]["routes"]["options"]["blackhole"]

    def test_name_is_merged_into_desired_tags(self):
        module = SimpleNamespace(params={"name": "main", "tags": {"Env": "prod"}})
        assert plugin.desired_tags(module) == {"Env": "prod", "Name": "main"}

    def test_name_tag_counts_toward_provider_limit(self):
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
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["msg"], "tags must contain at most 50 entries")

    def test_absent_does_not_validate_unused_routes(self):
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

    def test_create_without_tags_does_not_gate_tag_specifications(self):
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

    def test_name_only_create_does_not_gate_separate_tag_api(self):
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

        self.assertEqual(
            require_methods.call_args.args[3],
            {
                "describe_transit_gateway_route_tables": (
                    "Filters",
                    "MaxResults",
                    "NextToken",
                    "TransitGatewayRouteTableIds",
                )
            },
        )

    def test_static_route_matches_attachment(self):
        route = {
            "State": "active",
            "Type": "static",
            "TransitGatewayAttachments": [{"TransitGatewayAttachmentId": "tgw-attach-1"}],
        }
        assert plugin.desired_route_matches(route, {"transit_gateway_attachment_id": "tgw-attach-1"})
        assert not plugin.desired_route_matches(route, {"transit_gateway_attachment_id": "tgw-attach-2"})

    def test_check_mode_builds_blackhole_route(self):
        assert plugin.check_mode_route({"blackhole": True, "destination_cidr_block": "10.0.0.0/8"}) == {
            "DestinationCidrBlock": "10.0.0.0/8",
            "State": "blackhole",
            "TransitGatewayAttachments": [],
            "Type": "static",
        }

    def test_propagated_route_is_not_deleted(self):
        client = Mock()
        module = SimpleNamespace(params={"wait": False}, check_mode=False)
        route = {"State": "active", "Type": "propagated"}
        with patch.object(plugin, "get_route", return_value=route):
            changed, returned = plugin.ensure_route_absent(client, module, "tgw-rtb-1", "10.0.0.0/8")

        self.assertFalse(changed)
        self.assertIs(returned, route)
        client.delete_transit_gateway_route.assert_not_called()

    def test_changed_static_route_is_replaced_in_place(self):
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
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        client.replace_transit_gateway_route.assert_called_once_with(
            DestinationCidrBlock="10.0.0.0/8",
            TransitGatewayAttachmentId="tgw-attach-new",
            TransitGatewayRouteTableId="tgw-rtb-1",
            aws_retry=True,
        )
        client.create_transit_gateway_route.assert_not_called()

    def test_new_table_waits_before_routes_when_final_wait_is_disabled(self):
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
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        wait.assert_called_once_with(client, module, "tgw-rtb-1", {"available"})

    def test_absent_waits_for_pending_table_when_final_wait_is_disabled(self):
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
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_absent(client, module)
        wait_for_route_table.assert_called_once_with(client, module, "tgw-rtb-1", {"available"})
        client.delete_transit_gateway_route_table.assert_called_once_with(
            TransitGatewayRouteTableId="tgw-rtb-1", aws_retry=True
        )

    def test_deleting_route_waits_before_recreation_when_final_wait_is_disabled(self):
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
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        wait.assert_called_once_with(client, module, "tgw-rtb-1", "10.0.0.0/8")
        client.create_transit_gateway_route.assert_called_once()

    def test_routes_require_unique_destinations_and_a_target(self):
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
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_false_blackhole_allows_attachment(self):
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

    def test_route_search_uses_all_paginated_results(self):
        client = Mock()
        routes = [{"DestinationCidrBlock": "10.0.0.0/8"}]
        with (
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"Routes": routes},
            ) as query,
            patch.object(plugin, "require_client_methods"),
        ):
            result = plugin.search_routes(
                client,
                FakeModule({}),
                "tgw-rtb-1",
                {"type": ["static"]},
            )
        self.assertEqual(result, routes)
        self.assertEqual(query.call_args.args[1], "search_transit_gateway_routes")
        client.search_transit_gateway_routes.assert_not_called()

    def test_purge_removes_only_undesired_static_routes(self):
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
            patch.object(
                plugin,
                "static_routes",
                side_effect=[[desired_route, stale_route], [desired_route]],
            ),
            patch.object(plugin, "ensure_route_absent", return_value=(True, None)) as remove,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        remove.assert_called_once_with(client, module, "tgw-rtb-1", "192.0.2.0/24")
        self.assertEqual(
            [route["destination_cidr_block"] for route in raised.exception.values["routes"]],
            ["10.0.0.0/8"],
        )
