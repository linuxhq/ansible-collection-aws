from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule_associate as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Route53ResolverRuleAssociateTests(TestCase):
    def test_create_rereads_association_when_response_is_lean(self):
        client = Mock(associate_resolver_rule=Mock(return_value={}))
        module = FakeModule(
            {
                "name": "main",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
                "wait": False,
            }
        )
        association = {
            "Id": "rslvr-rrassoc-1",
            "Name": "main",
            "ResolverRuleId": "rslvr-rr-1",
            "VPCId": "vpc-1",
        }
        with (
            patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", side_effect=[None, association]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(raised.exception.values["resolver_rule_association_id"], "rslvr-rrassoc-1")

    def test_wait_rejects_malformed_get_response(self):
        client = Mock(get_resolver_rule_association=Mock(return_value=[]))
        module = FakeModule(
            {
                "name": "main",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
            }
        )
        with (
            patch.object(plugin, "run_waiter"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.wait_for_resolver_rule_association_status(
                client,
                module,
                "rslvr-rrassoc-1",
                {"complete"},
            )

        self.assertIn("invalid resolver rule association", raised.exception.values["msg"])

    def test_list_rejects_malformed_and_ambiguous_associations(self):
        module = FakeModule(
            {
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
            }
        )
        valid = {
            "Name": "main",
            "ResolverRuleId": "rslvr-rr-1",
            "VPCId": "vpc-1",
        }
        cases = [
            ([valid], "without a valid ID"),
            (
                [dict(valid, Id="rslvr-rrassoc-1"), dict(valid, Id="rslvr-rrassoc-2")],
                "Multiple AWS Route53 Resolver rule associations",
            ),
            ([dict(valid, Id="rslvr-rrassoc-1", VPCId="vpc-2")], "unexpected resolver rule association VPCId"),
        ]
        for associations, message in cases:
            with (
                self.subTest(message=message),
                patch.object(plugin, "query_list", return_value=associations),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.get_resolver_rule_association_by_rule_and_vpc(Mock(), module)
            self.assertIn(message, raised.exception.values["msg"])

    def test_check_mode_replacement_does_not_return_stale_id(self):
        module = FakeModule(
            {
                "name": "new-name",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
            },
            check_mode=True,
        )
        current = {
            "Id": "old-association",
            "Name": "old-name",
            "ResolverRuleId": "rslvr-rr-1",
            "VPCId": "vpc-1",
        }
        with (
            patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertNotIn("resolver_rule_association_id", raised.exception.values)

    def test_absent_does_not_require_name(self):
        module = FakeModule(
            {
                "resolver_rule_id": "rslvr-rr-1",
                "state": "absent",
                "vpc_id": "vpc-1",
                "wait": False,
            }
        )
        with (
            patch.object(
                plugin,
                "get_resolver_rule_association_by_rule_and_vpc",
                return_value=None,
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(Mock(), module)

        self.assertFalse(raised.exception.values["changed"])
        self.assertNotIn("name", raised.exception.values)

    def test_absent_tolerates_association_disappearing_during_delete(self):
        client = Mock()
        client.disassociate_resolver_rule.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DisassociateResolverRule",
        )
        module = FakeModule(
            {
                "name": "association",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
                "wait": False,
            }
        )
        with (
            patch.object(
                plugin,
                "get_resolver_rule_association_by_rule_and_vpc",
                return_value={"Id": "rslvr-rrassoc-1"},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])

    def test_absent_waits_for_deleting_association_without_disassociating(self):
        client = Mock()
        module = FakeModule(
            {
                "resolver_rule_id": "rslvr-rr-1",
                "state": "absent",
                "vpc_id": "vpc-1",
                "wait": True,
            }
        )
        with (
            patch.object(
                plugin,
                "get_resolver_rule_association_by_rule_and_vpc",
                return_value={"Id": "rslvr-rrassoc-1", "Status": "DELETING"},
            ),
            patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertFalse(raised.exception.values["changed"])
        client.disassociate_resolver_rule.assert_not_called()
        wait_for_status.assert_called_once_with(client, module, "rslvr-rrassoc-1", {"deleted"})

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["wait_timeout"]["default"] == 300
        assert ("state", "present", ["name"]) in options["required_if"]
        assert {
            acceptor["expected"]
            for acceptor in plugin.ROUTE53_RESOLVER_RULE_ASSOCIATION_WAITER_MODEL_DATA[
                "resolver_rule_association_complete"
            ]["acceptors"]
        } == {"COMPLETE", "CREATING", "DELETING", "FAILED", "OVERRIDDEN"}

    def test_check_mode_predicts_rule_association(self):
        module = FakeModule(
            {
                "name": "main",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
            },
            check_mode=True,
        )
        with (
            patch.object(
                plugin,
                "get_resolver_rule_association_by_rule_and_vpc",
                return_value=None,
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["resolver_rule_association"]["vpc_id"], "vpc-1")

    def test_replacement_waits_for_deletion_when_final_wait_is_disabled(self):
        client = Mock()
        client.associate_resolver_rule.return_value = {"ResolverRuleAssociation": {"Id": "new-association"}}
        module = FakeModule(
            {
                "name": "new-name",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
                "wait": False,
            }
        )
        current = {
            "Id": "old-association",
            "Name": "old-name",
            "ResolverRuleId": "rslvr-rr-1",
            "Status": "OVERRIDDEN",
            "VPCId": "vpc-1",
        }
        with (
            patch.object(
                plugin,
                "get_resolver_rule_association_by_rule_and_vpc",
                return_value=current,
            ),
            patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        wait_for_status.assert_called_once_with(client, module, "old-association", {"deleted"})

    def test_deleting_association_waits_before_recreation(self):
        client = Mock()
        client.associate_resolver_rule.return_value = {"ResolverRuleAssociation": {"Id": "new-association"}}
        module = FakeModule(
            {
                "name": "main",
                "resolver_rule_id": "rslvr-rr-1",
                "vpc_id": "vpc-1",
                "wait": False,
            }
        )
        deleting = {"Id": "old-association", "Status": "DELETING"}
        with (
            patch.object(
                plugin,
                "get_resolver_rule_association_by_rule_and_vpc",
                side_effect=[deleting, None],
            ),
            patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        wait_for_status.assert_called_once_with(client, module, "old-association", {"deleted"})
        client.associate_resolver_rule.assert_called_once()

    def test_present_validates_bounds_for_internal_replacement_wait(self):
        module = FakeModule(
            {
                "name": "main",
                "resolver_rule_id": "rslvr-rr-1",
                "state": "present",
                "vpc_id": "vpc-1",
                "wait": False,
                "wait_delay": 0,
                "wait_timeout": 300,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("wait_delay", raised.exception.values["msg"])

    def test_present_rejects_invalid_name_before_api_calls(self):
        module = FakeModule(
            {
                "name": "123",
                "resolver_rule_id": "rslvr-rr-1",
                "state": "present",
                "vpc_id": "vpc-1",
                "wait": False,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("valid resolver rule association name", raised.exception.values["msg"])
