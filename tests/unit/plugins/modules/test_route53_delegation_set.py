from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_delegation_set as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Route53DelegationSetTests(TestCase):
    def test_absent_tolerates_set_disappearing_during_delete(self):
        client = Mock()
        client.delete_reusable_delegation_set.side_effect = plugin.ClientError(
            {"Error": {"Code": "NoSuchDelegationSet", "Message": "gone"}},
            "DeleteReusableDelegationSet",
        )
        module = FakeModule({"name": "main"})
        with (
            patch.object(
                plugin,
                "get_reusable_delegation_set",
                return_value={"Id": "delegation-set-1"},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["name"]["required"] is True

    def test_absent_rejects_empty_name(self):
        module = FakeModule({"name": "", "state": "absent"})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["msg"], "name must be 1 to 128 characters")

    def test_check_mode_predicts_delegation_set(self):
        module = FakeModule({"name": "example"}, check_mode=True)
        with (
            patch.object(plugin, "get_reusable_delegation_set", return_value=None),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["delegation_set"],
            {"caller_reference": "example"},
        )

    def test_lookup_uses_all_paginated_delegation_sets(self):
        client = Mock()
        module = FakeModule({"name": "example"})
        with patch.object(
            plugin,
            "query_list",
            return_value=[
                {"CallerReference": "other", "Id": "delegation-0"},
                {"CallerReference": "example", "Id": "delegation-1"},
            ],
        ) as query:
            result = plugin.get_reusable_delegation_set(client, module)
        self.assertEqual(result["Id"], "delegation-1")
        query.assert_called_once()

    def test_lookup_rejects_malformed_delegation_sets(self):
        module = FakeModule({"name": "example"})
        for delegation_sets in ([None], [{"CallerReference": "example"}]):
            with (
                self.subTest(delegation_sets=delegation_sets),
                patch.object(plugin, "query_list", return_value=delegation_sets),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.get_reusable_delegation_set(Mock(), module)

            self.assertEqual(
                raised.exception.values["msg"],
                "Unable to list AWS Route53 reusable delegation sets: AWS returned an invalid response",
            )

    def test_create_uses_lookup_when_response_is_malformed(self):
        client = Mock()
        client.create_reusable_delegation_set.return_value = None
        module = FakeModule({"name": "example"})
        with (
            patch.object(
                plugin,
                "get_reusable_delegation_set",
                side_effect=[None, {"CallerReference": "example", "Id": "delegation-1"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["delegation_set_id"], "delegation-1")

    def test_listing_requires_pagination_parameters(self):
        client = Mock()
        module = FakeModule({"name": "example", "state": "absent"})
        module.client = Mock(return_value=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "ensure_absent"),
        ):
            plugin.main()
        require_methods.assert_called_once_with(
            module,
            client,
            "Route53",
            {
                "list_reusable_delegation_sets": ("Marker", "MaxItems"),
                "delete_reusable_delegation_set": ("Id",),
            },
        )
