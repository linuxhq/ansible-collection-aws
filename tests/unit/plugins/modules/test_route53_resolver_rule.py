from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class Route53ResolverRuleTests(TestCase):
    def test_get_rejects_malformed_response(self):
        client = Mock(get_resolver_rule=Mock(return_value=[]))
        with self.assertRaises(ModuleFail) as raised:
            plugin.get_resolver_rule(client, FakeModule({"name": "rule"}), "rslvr-rr-1")

        self.assertEqual(
            raised.exception.values["msg"],
            "get_resolver_rule: AWS returned an invalid resolver rule",
        )

    def test_create_rereads_rule_when_response_is_lean(self):
        client = Mock(create_resolver_rule=Mock(return_value={}))
        module = FakeModule({"state": "present", "tags": None, "wait": False})
        desired = {
            "domain_name": "example.com",
            "name": "main",
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "target_ips": [{"ip": "192.0.2.1"}],
        }
        rule = {"Id": "rslvr-rr-1"}
        with patch.object(plugin, "get_resolver_rule_by_name", return_value=rule) as get:
            result = plugin.create_resolver_rule(client, module, desired)

        get.assert_called_once_with(client, module)
        self.assertEqual(result["DomainName"], "example.com")
        self.assertEqual(result["Id"], "rslvr-rr-1")

    def test_list_by_name_rejects_malformed_rule(self):
        module = FakeModule({"name": "main", "state": "absent"})
        with (
            patch.object(plugin, "query_list", return_value=[{"Name": "main"}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.get_resolver_rule_by_name(Mock(), module)

        self.assertIn("without a valid ID", raised.exception.values["msg"])

    def test_rule_and_tag_validation_rejects_malformed_entries(self):
        module = FakeModule({"name": "main"})
        rule = {
            "DomainName": "example.com",
            "Id": "rslvr-rr-1",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Port": 53}],
        }
        with self.assertRaises(ModuleFail) as target_raised:
            plugin.validate_resolver_rule(module, rule, "get_resolver_rule", require_details=True)
        self.assertIn("without an IP address", target_raised.exception.values["msg"])

        with self.assertRaises(ModuleFail) as tag_raised:
            plugin.validate_tags(module, [{"Key": "Name"}])
        self.assertIn("invalid tag", tag_raised.exception.values["msg"])

    def test_absent_waits_for_deleting_rule_without_deleting_again(self):
        client = Mock()
        module = FakeModule({"name": "rule", "wait": True})
        rule = {"Id": "rslvr-rr-1", "Status": "DELETING"}
        with (
            patch.object(plugin, "get_resolver_rule_by_name", return_value=rule),
            patch.object(plugin, "delete_resolver_rule") as delete,
            patch.object(plugin, "wait_for_resolver_rule_status") as wait,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertFalse(raised.exception.values["changed"])
        delete.assert_not_called()
        wait.assert_called_once_with(client, module, "rslvr-rr-1", {"deleted"})

    def test_replacement_delete_waits_when_final_wait_is_disabled(self):
        client = Mock()
        module = FakeModule({"name": "rule", "wait": False})
        with patch.object(plugin, "wait_for_resolver_rule_status") as wait:
            plugin.delete_resolver_rule(client, module, {"Id": "rslvr-rr-1"}, always=True)
        wait.assert_called_once_with(client, module, "rslvr-rr-1", {"deleted"})

    def test_delete_tolerates_rule_disappearing(self):
        client = Mock()
        client.delete_resolver_rule.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DeleteResolverRule",
        )
        module = FakeModule({"name": "rule", "wait": True})
        with patch.object(plugin, "wait_for_resolver_rule_status") as wait:
            plugin.delete_resolver_rule(client, module, {"Id": "rslvr-rr-1"})
        wait.assert_not_called()

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["rule_type"]["choices"] == ["forward"]
        assert options["argument_spec"]["target_ips"]["required_one_of"] == [["ip", "ipv6"]]

    def test_empty_tags_do_not_gate_tag_resource(self):
        client = Mock()
        module = FakeModule(
            {
                "domain_name": "example.com",
                "name": "rule",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "forward",
                "state": "present",
                "tags": {},
                "target_ips": [{"ip": "192.0.2.1", "port": 53}],
                "wait": False,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "ensure_present"),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "require_positive_wait_bounds"),
        ):
            plugin.main()

        methods = require_methods.call_args.args[3]
        self.assertNotIn("tag_resource", methods)
        self.assertIn("untag_resource", methods)

    def test_omitted_tags_do_not_gate_create_tags_parameter(self):
        client = Mock()
        module = FakeModule(
            {
                "domain_name": "example.com",
                "name": "rule",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "forward",
                "state": "present",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1", "port": 53}],
                "wait": False,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "ensure_present"),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "require_positive_wait_bounds"),
        ):
            plugin.main()

        methods = require_methods.call_args.args[3]
        self.assertNotIn("Tags", methods["create_resolver_rule"])

    def test_empty_target_ips_are_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "domain_name": "example.com",
                "name": "rule",
                "resolver_endpoint_id": "rslvr-out-1",
                "state": "present",
                "tags": None,
                "target_ips": [],
            },
            "target_ips must contain at least one entry",
        )

    def test_invalid_name_is_rejected_when_absent(self):
        assert_module_rejects(
            self,
            plugin,
            {"name": "123", "state": "absent", "tags": None},
            "name must be a valid resolver rule name of at most 64 characters",
        )

    def test_no_wait_present_still_validates_internal_wait_bounds(self):
        module = FakeModule(
            {
                "domain_name": "example.com",
                "name": "rule",
                "resolver_endpoint_id": "rslvr-out-1",
                "state": "present",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1", "port": 53}],
                "wait": False,
                "wait_delay": 0,
                "wait_timeout": 300,
            },
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["msg"], "wait_delay must be 1 or greater")

    def test_replacement_sensitive_limits_are_rejected(self):
        base = {
            "domain_name": "example.com",
            "name": "rule",
            "resolver_endpoint_id": "rslvr-out-1",
            "state": "present",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1", "port": 53}],
        }
        cases = (
            (
                dict(base, name="123"),
                "name must be a valid resolver rule name of at most 64 characters",
            ),
            (
                dict(base, domain_name=""),
                "domain_name must contain 1 to 256 characters",
            ),
            (
                dict(base, resolver_endpoint_id=""),
                "resolver_endpoint_id must contain 1 to 64 characters",
            ),
            (
                dict(base, tags={str(index): "" for index in range(201)}),
                "tags must contain at most 200 entries",
            ),
            (
                dict(
                    base,
                    target_ips=[
                        {
                            "ip": "192.0.2.1",
                            "port": 53,
                            "server_name_indication": "s" * 256,
                        }
                    ],
                ),
                "target_ips[].server_name_indication must contain at most 255 characters",
            ),
        )
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_target_port_bounds_are_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "domain_name": "example.com",
                "name": "rule",
                "resolver_endpoint_id": "rslvr-out-1",
                "state": "present",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1", "port": 65536}],
            },
            "target_ips[].port must be between 0 and 65535",
        )

    def test_target_ip_versions_are_rejected(self):
        for target, message in (
            (
                {"ip": "2001:db8::1", "port": 53},
                "target_ips[].ip must be a valid IPv4 address",
            ),
            (
                {"ipv6": "192.0.2.1", "port": 53},
                "target_ips[].ipv6 must be a valid IPv6 address",
            ),
        ):
            with self.subTest(message=message):
                assert_module_rejects(
                    self,
                    plugin,
                    {
                        "domain_name": "example.com",
                        "name": "rule",
                        "resolver_endpoint_id": "rslvr-out-1",
                        "state": "present",
                        "tags": None,
                        "target_ips": [target],
                    },
                    message,
                )

    def test_rule_comparison_normalizes_domain_and_target_defaults(self):
        self.assertEqual(
            plugin.comparable_rule(
                {
                    "DomainName": "Example.COM.",
                    "ResolverEndpointId": "rslvr-out-1",
                    "RuleType": "FORWARD",
                    "TargetIps": [{"Ip": "192.0.2.1"}, {"Ip": "192.0.2.1"}],
                }
            ),
            {
                "domain_name": "example.com",
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "FORWARD",
                "target_ips": [{"ip": "192.0.2.1", "port": 53, "protocol": "Do53"}],
            },
        )

    def test_create_token_changes_with_desired_rule(self):
        client = Mock(
            create_resolver_rule=Mock(
                side_effect=[
                    {"ResolverRule": {"Id": "rule-1"}},
                    {"ResolverRule": {"Id": "rule-2"}},
                ]
            )
        )
        module = FakeModule({"tags": {"Env": "test"}, "wait": False})
        desired = {
            "domain_name": "example.com",
            "name": "main",
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "target_ips": [{"ip": "192.0.2.1"}],
        }
        created = plugin.create_resolver_rule(client, module, desired)
        plugin.create_resolver_rule(client, module, dict(desired, domain_name="changed.example.com"))

        tokens = [call.kwargs["CreatorRequestId"] for call in client.create_resolver_rule.call_args_list]
        self.assertNotEqual(tokens[0], tokens[1])
        self.assertEqual(created["Tags"], [{"Key": "Env", "Value": "test"}])

    def test_absent_lookup_does_not_fetch_unused_rule_details(self):
        client = Mock()
        module = FakeModule({"name": "main", "state": "absent"})
        summary = {"Id": "rslvr-rr-1", "Name": "main"}
        with patch.object(plugin, "query_list", return_value=[summary]):
            self.assertEqual(plugin.get_resolver_rule_by_name(client, module), summary)

        client.get_resolver_rule.assert_not_called()
        client.list_tags_for_resource.assert_not_called()

    def test_domain_change_recreates_the_rule(self):
        client = Mock()
        module = FakeModule(
            {
                "domain_name": "new.example.com",
                "name": "main",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "forward",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1"}],
                "wait": False,
            }
        )
        current = {
            "DomainName": "old.example.com",
            "Id": "rslvr-rr-1",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Ip": "192.0.2.1"}],
        }
        replacement = dict(current, DomainName="new.example.com")
        with (
            patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
            patch.object(plugin, "delete_resolver_rule") as delete,
            patch.object(plugin, "create_resolver_rule", return_value=replacement) as create,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        delete.assert_called_once_with(client, module, current, always=True)
        create.assert_called_once()
        client.update_resolver_rule.assert_not_called()

    def test_deleting_rule_waits_before_recreation_with_final_wait_disabled(self):
        client = Mock()
        module = FakeModule(
            {
                "domain_name": "example.com",
                "name": "main",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "forward",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1"}],
                "wait": False,
            }
        )
        deleting = {"Id": "rslvr-rr-old", "Name": "main", "Status": "DELETING"}
        replacement = {
            "DomainName": "example.com",
            "Id": "rslvr-rr-new",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Ip": "192.0.2.1"}],
        }
        with (
            patch.object(plugin, "get_resolver_rule_by_name", side_effect=[deleting, None]),
            patch.object(plugin, "wait_for_resolver_rule_status") as wait_for_status,
            patch.object(plugin, "create_resolver_rule", return_value=replacement) as create,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        wait_for_status.assert_called_once_with(client, module, "rslvr-rr-old", {"deleted"})
        create.assert_called_once()

    def test_update_rereads_rule_when_response_is_lean(self):
        client = Mock(update_resolver_rule=Mock(return_value={}))
        module = FakeModule(
            {
                "domain_name": "example.com",
                "name": "main",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-2",
                "rule_type": "forward",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1"}],
                "wait": False,
            }
        )
        current = {
            "DomainName": "example.com",
            "Id": "rslvr-rr-1",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Ip": "192.0.2.1"}],
        }
        updated = dict(current, ResolverEndpointId="rslvr-out-2")
        with (
            patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
            patch.object(plugin, "get_resolver_rule", return_value=updated) as get,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        get.assert_called_once_with(client, module, "rslvr-rr-1")

    def test_check_mode_replacement_does_not_return_stale_id(self):
        module = FakeModule(
            {
                "domain_name": "new.example.com",
                "name": "main",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "forward",
                "tags": None,
                "target_ips": [{"ip": "192.0.2.1"}],
                "wait": False,
            },
            check_mode=True,
        )
        current = {
            "DomainName": "old.example.com",
            "Id": "rslvr-rr-old",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Ip": "192.0.2.1"}],
        }
        with (
            patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertNotIn("resolver_rule_id", raised.exception.values)

    def test_tag_change_rejects_rule_without_arn(self):
        module = FakeModule(
            {
                "domain_name": "example.com",
                "name": "main",
                "purge_tags": True,
                "resolver_endpoint_id": "rslvr-out-1",
                "rule_type": "forward",
                "tags": {"Name": "main"},
                "target_ips": [{"ip": "192.0.2.1"}],
                "wait": False,
            }
        )
        current = {
            "DomainName": "example.com",
            "Id": "rslvr-rr-1",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Ip": "192.0.2.1"}],
        }
        with (
            patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertIn("invalid rule ARN", raised.exception.values["msg"])
