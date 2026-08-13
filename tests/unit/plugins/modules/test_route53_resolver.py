from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
    assert_module_rejects,
)


class Route53ResolverTests(TestCase):
    def test_absent_waits_for_deleting_endpoint_without_deleting_again(self):
        client = Mock()
        module = FakeModule({"name": "endpoint", "wait": True})
        endpoint = {"Id": "rslvr-endpt-1", "Status": "DELETING"}
        with (
            patch.object(
                plugin, "get_resolver_endpoint_by_name", return_value=endpoint
            ),
            patch.object(plugin, "delete_resolver_endpoint") as delete,
            patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertFalse(raised.exception.values["changed"])
        delete.assert_not_called()
        wait.assert_called_once_with(client, module, "rslvr-endpt-1", {"deleted"})

    def test_replacement_delete_waits_when_final_wait_is_disabled(self):
        client = Mock()
        module = FakeModule({"name": "endpoint", "wait": False})
        with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
            plugin.delete_resolver_endpoint(
                client, module, {"Id": "rslvr-endpt-1"}, always=True
            )
        wait.assert_called_once_with(client, module, "rslvr-endpt-1", {"deleted"})

    def test_delete_tolerates_endpoint_disappearing(self):
        client = Mock()
        client.delete_resolver_endpoint.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DeleteResolverEndpoint",
        )
        module = FakeModule({"name": "endpoint", "wait": True})
        with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
            plugin.delete_resolver_endpoint(client, module, {"Id": "rslvr-endpt-1"})
        wait.assert_not_called()

    def test_module_contract(self):
        assert_module_contract(self, plugin)

    def test_absent_rejects_invalid_name(self):
        assert_module_rejects(
            self,
            plugin,
            {"name": "", "state": "absent", "tags": None},
            "name must be a valid resolver endpoint name of at most 64 characters",
        )

    def test_empty_tags_do_not_gate_tag_resource(self):
        client = Mock()
        module = FakeModule(
            {
                "direction": "outbound",
                "ip_addresses": [
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
                "name": "endpoint",
                "protocols": ["do53"],
                "purge_tags": True,
                "resolver_endpoint_type": "ipv4",
                "security_group_ids": ["sg-1"],
                "state": "present",
                "tags": {},
                "wait": False,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "ensure_present"),
        ):
            plugin.main()

        methods = require_methods.call_args.args[3]
        self.assertNotIn("tag_resource", methods)
        self.assertIn("untag_resource", methods)

    def test_endpoint_list_limits_are_rejected(self):
        base = {
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "endpoint",
            "protocols": ["Do53"],
            "security_group_ids": ["sg-1"],
            "state": "present",
            "tags": None,
        }
        cases = [
            (
                dict(base, name="123"),
                "name must be a valid resolver endpoint name of at most 64 characters",
            ),
            (
                dict(base, ip_addresses=[{"subnet_id": "subnet-1"}]),
                "ip_addresses must contain 2 to 20 entries",
            ),
            (
                dict(
                    base,
                    ip_addresses=[
                        {"subnet_id": "subnet-1"},
                        {"subnet_id": "subnet-1"},
                    ],
                ),
                "ip_addresses entries must be unique",
            ),
            (dict(base, protocols=[]), "protocols must contain 1 or 2 entries"),
            (
                dict(base, security_group_ids=[]),
                "security_group_ids must contain at least one entry",
            ),
            (
                dict(base, security_group_ids=["s" * 65]),
                "security_group_ids entries must contain 1 to 64 characters",
            ),
            (
                dict(
                    base,
                    ip_addresses=[
                        {"subnet_id": "s" * 33},
                        {"subnet_id": "subnet-2"},
                    ],
                ),
                "ip_addresses[].subnet_id must contain 1 to 32 characters",
            ),
            (
                dict(
                    base,
                    ip_addresses=[
                        {"ip": "2001:db8::1", "subnet_id": "subnet-1"},
                        {"subnet_id": "subnet-2"},
                    ],
                ),
                "ip_addresses[].ip must be a valid IPv4 address",
            ),
            (
                dict(
                    base,
                    ip_addresses=[
                        {"ipv6": "192.0.2.1", "subnet_id": "subnet-1"},
                        {"subnet_id": "subnet-2"},
                    ],
                ),
                "ip_addresses[].ipv6 must be a valid IPv6 address",
            ),
            (
                dict(base, tags={str(index): "" for index in range(201)}),
                "tags must contain at most 200 entries",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_endpoint_comparison_ignores_order_and_response_fields(self):
        endpoint = {
            "Direction": "OUTBOUND",
            "IpAddresses": [
                {"SubnetId": "subnet-b", "IpId": "rni-2"},
                {"SubnetId": "subnet-a", "Ip": "192.0.2.1", "Status": "ATTACHED"},
            ],
            "Protocols": ["DoH", "Do53", "DoH"],
            "ResolverEndpointType": "IPV4",
            "SecurityGroupIds": ["sg-b", "sg-a", "sg-b"],
            "Status": "OPERATIONAL",
        }
        self.assertEqual(
            plugin.comparable_endpoint(endpoint),
            {
                "direction": "OUTBOUND",
                "ip_addresses": [
                    {"ip": "192.0.2.1", "subnet_id": "subnet-a"},
                    {"subnet_id": "subnet-b"},
                ],
                "protocols": ["Do53", "DoH"],
                "resolver_endpoint_type": "IPV4",
                "security_group_ids": ["sg-a", "sg-b"],
            },
        )

    def test_auto_assigned_ip_addresses_are_idempotent(self):
        client = Mock()
        module = FakeModule(
            {
                "direction": "outbound",
                "ip_addresses": [
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
                "name": "main",
                "protocols": ["do53"],
                "purge_tags": True,
                "resolver_endpoint_type": "ipv4",
                "security_group_ids": ["sg-1"],
                "tags": None,
                "wait": False,
            }
        )
        current = {
            "Direction": "OUTBOUND",
            "Id": "rslvr-1",
            "IpAddresses": [
                {"Ip": "192.0.2.1", "SubnetId": "subnet-1"},
                {"Ip": "192.0.2.2", "SubnetId": "subnet-2"},
            ],
            "Protocols": ["Do53"],
            "ResolverEndpointType": "IPV4",
            "SecurityGroupIds": ["sg-1"],
        }
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
            patch.object(
                plugin,
                "resolver_endpoint_with_ip_addresses",
                side_effect=lambda *args: args[2],
            ),
            patch.object(
                plugin, "resolver_endpoint_with_tags", side_effect=lambda *args: args[2]
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertFalse(raised.exception.values["changed"])
        client.associate_resolver_endpoint_ip_address.assert_not_called()
        client.disassociate_resolver_endpoint_ip_address.assert_not_called()

    def test_check_mode_preserves_unchanged_auto_assigned_addresses(self):
        module = FakeModule(
            {
                "direction": "outbound",
                "ip_addresses": [
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
                "name": "main",
                "protocols": ["doh"],
                "purge_tags": True,
                "resolver_endpoint_type": "ipv4",
                "security_group_ids": ["sg-1"],
                "tags": None,
                "wait": False,
            },
            check_mode=True,
        )
        current = {
            "Direction": "OUTBOUND",
            "Id": "rslvr-1",
            "IpAddresses": [
                {"Ip": "192.0.2.1", "SubnetId": "subnet-1"},
                {"Ip": "192.0.2.2", "SubnetId": "subnet-2"},
            ],
            "Protocols": ["Do53"],
            "ResolverEndpointType": "IPV4",
            "SecurityGroupIds": ["sg-1"],
        }
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
            patch.object(
                plugin,
                "resolver_endpoint_with_ip_addresses",
                side_effect=lambda *args: args[2],
            ),
            patch.object(
                plugin, "resolver_endpoint_with_tags", side_effect=lambda *args: args[2]
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["resolver_endpoint"]["ip_addresses"],
            [
                {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
                {"ip": "192.0.2.2", "subnet_id": "subnet-2"},
            ],
        )

    def test_create_token_changes_with_desired_endpoint(self):
        client = Mock(
            create_resolver_endpoint=Mock(
                side_effect=[
                    {"ResolverEndpoint": {"Id": "endpoint-1"}},
                    {"ResolverEndpoint": {"Id": "endpoint-2"}},
                ]
            )
        )
        module = FakeModule({"tags": None, "wait": False})
        desired = {
            "direction": "OUTBOUND",
            "ip_addresses": [{"subnet_id": "subnet-1"}],
            "name": "main",
            "protocols": ["Do53"],
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
        }
        created = plugin.create_resolver_endpoint(client, module, desired)
        plugin.create_resolver_endpoint(
            client, module, dict(desired, direction="INBOUND")
        )

        tokens = [
            call.kwargs["CreatorRequestId"]
            for call in client.create_resolver_endpoint.call_args_list
        ]
        self.assertNotEqual(tokens[0], tokens[1])
        self.assertEqual(created["IpAddresses"], [{"SubnetId": "subnet-1"}])

    def test_ip_reconciliation_adds_and_removes_only_differences(self):
        client = Mock()
        module = Mock(params={"wait": False})
        endpoint = {
            "Id": "rslvr-1",
            "IpAddresses": [{"IpId": "rni-old", "SubnetId": "subnet-old"}],
        }
        desired = {
            "name": "main",
            "ip_addresses": [{"subnet_id": "subnet-new"}],
        }
        with (
            patch.object(
                plugin,
                "wait_for_resolver_endpoint_status",
            ) as wait_for_resolver_endpoint_status,
        ):
            result = plugin.reconcile_resolver_endpoint_ip_addresses(
                client, module, endpoint, desired
            )

        client.associate_resolver_endpoint_ip_address.assert_called_once_with(
            IpAddress={"SubnetId": "subnet-new"},
            ResolverEndpointId="rslvr-1",
            aws_retry=True,
        )
        client.disassociate_resolver_endpoint_ip_address.assert_called_once_with(
            IpAddress={"IpId": "rni-old", "SubnetId": "subnet-old"},
            ResolverEndpointId="rslvr-1",
            aws_retry=True,
        )
        wait_for_resolver_endpoint_status.assert_called_once_with(
            client, module, "rslvr-1", {"operational"}
        )
        self.assertEqual(result["Id"], "rslvr-1")
        self.assertEqual(result["IpAddresses"], [{"SubnetId": "subnet-new"}])

    def test_ip_replacements_stay_within_provider_count_bounds(self):
        for count, first_operation in ((2, "associate"), (20, "disassociate")):
            current = [
                {"IpId": f"rni-{index}", "SubnetId": f"subnet-{index}"}
                for index in range(count)
            ]
            desired = {
                "name": "main",
                "ip_addresses": [
                    {"subnet_id": f"subnet-{index}"} for index in range(1, count)
                ]
                + [{"subnet_id": "subnet-new"}],
            }
            client = Mock()
            with (
                self.subTest(count=count),
                patch.object(plugin, "wait_for_resolver_endpoint_status"),
            ):
                plugin.reconcile_resolver_endpoint_ip_addresses(
                    client,
                    Mock(params={"wait": False}),
                    {"Id": "rslvr-1", "IpAddresses": current},
                    desired,
                )
            self.assertTrue(
                client.method_calls[0][0].startswith(first_operation),
                client.method_calls,
            )

    def test_direction_change_recreates_the_endpoint(self):
        client = Mock()
        module = FakeModule(
            {
                "direction": "outbound",
                "ip_addresses": [
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
                "name": "main",
                "protocols": ["do53"],
                "purge_tags": True,
                "resolver_endpoint_type": "ipv4",
                "security_group_ids": ["sg-1"],
                "tags": None,
                "wait": False,
            }
        )
        current = {
            "Direction": "INBOUND",
            "Id": "rslvr-old",
            "IpAddresses": [
                {"SubnetId": "subnet-1"},
                {"SubnetId": "subnet-2"},
            ],
            "Protocols": ["Do53"],
            "ResolverEndpointType": "IPV4",
            "SecurityGroupIds": ["sg-1"],
        }
        replacement = dict(current, Direction="OUTBOUND", Id="rslvr-new")
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
            patch.object(
                plugin,
                "resolver_endpoint_with_ip_addresses",
                side_effect=lambda *args: args[2],
            ),
            patch.object(
                plugin, "resolver_endpoint_with_tags", side_effect=lambda *args: args[2]
            ),
            patch.object(
                plugin,
                "reconcile_resolver_endpoint_ip_addresses",
                return_value=current,
            ),
            patch.object(plugin, "delete_resolver_endpoint") as delete,
            patch.object(
                plugin, "create_resolver_endpoint", return_value=replacement
            ) as create,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        delete.assert_called_once_with(client, module, current, always=True)
        create.assert_called_once()
        client.update_resolver_endpoint.assert_not_called()

    def test_no_wait_change_waits_for_operational_endpoint_and_rechecks(self):
        client = Mock()
        module = FakeModule(
            {
                "direction": "outbound",
                "ip_addresses": [
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
                "name": "main",
                "protocols": ["do53"],
                "purge_tags": True,
                "resolver_endpoint_type": "ipv4",
                "security_group_ids": ["sg-1"],
                "tags": None,
                "wait": False,
            }
        )
        transitioning = {
            "Direction": "INBOUND",
            "Id": "rslvr-1",
            "IpAddresses": [
                {"SubnetId": "subnet-1"},
                {"SubnetId": "subnet-2"},
            ],
            "Protocols": ["Do53"],
            "ResolverEndpointType": "IPV4",
            "SecurityGroupIds": ["sg-1"],
            "Status": "UPDATING",
        }
        active = dict(transitioning, Direction="OUTBOUND", Status="OPERATIONAL")
        with (
            patch.object(
                plugin,
                "get_resolver_endpoint_by_name",
                side_effect=[transitioning, active],
            ),
            patch.object(
                plugin,
                "resolver_endpoint_with_ip_addresses",
                side_effect=lambda *args: args[2],
            ),
            patch.object(
                plugin, "resolver_endpoint_with_tags", side_effect=lambda *args: args[2]
            ),
            patch.object(
                plugin, "wait_for_resolver_endpoint_status"
            ) as wait_for_status,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        wait_for_status.assert_called_once_with(
            client, module, "rslvr-1", {"operational"}
        )
        client.update_resolver_endpoint.assert_not_called()
        self.assertFalse(raised.exception.values["changed"])

    def test_waited_endpoint_is_enriched_before_ip_reconciliation(self):
        client = Mock()
        module = FakeModule(
            {
                "direction": "outbound",
                "ip_addresses": [
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
                "name": "main",
                "protocols": ["doh"],
                "purge_tags": True,
                "resolver_endpoint_type": "ipv4",
                "security_group_ids": ["sg-1"],
                "tags": None,
                "wait": True,
            }
        )
        current = {
            "Direction": "OUTBOUND",
            "Id": "rslvr-1",
            "IpAddresses": [
                {"SubnetId": "subnet-1"},
                {"SubnetId": "subnet-2"},
            ],
            "Protocols": ["Do53"],
            "ResolverEndpointType": "IPV4",
            "SecurityGroupIds": ["sg-1"],
        }
        updated = dict(current, Protocols=["DoH"])
        waited = {key: value for key, value in updated.items() if key != "IpAddresses"}
        client.update_resolver_endpoint.return_value = {"ResolverEndpoint": updated}
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
            patch.object(
                plugin, "resolver_endpoint_with_tags", side_effect=lambda *args: args[2]
            ),
            patch.object(
                plugin, "wait_for_resolver_endpoint_status", return_value=waited
            ),
            patch.object(
                plugin,
                "resolver_endpoint_with_ip_addresses",
                side_effect=[current, updated],
            ) as enrich,
            patch.object(
                plugin,
                "reconcile_resolver_endpoint_ip_addresses",
                return_value=updated,
            ) as reconcile,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        enrich.assert_called_with(client, module, waited)
        reconcile.assert_called_once_with(client, module, updated, ANY)
