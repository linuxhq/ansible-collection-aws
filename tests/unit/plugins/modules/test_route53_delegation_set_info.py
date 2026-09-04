from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_delegation_set_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Route53DelegationSetInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["id"]["type"] == "str"

    def test_id_uses_get_reusable_delegation_set(self):
        client = Mock(get_reusable_delegation_set=Mock(return_value={"DelegationSet": {"Id": "delegation-1"}}))
        module = FakeModule({"id": "delegation-1"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        require_methods.assert_called_once_with(
            module,
            client,
            "Route53",
            {"get_reusable_delegation_set": ("Id",)},
        )
        client.get_reusable_delegation_set.assert_called_once_with(Id="delegation-1", aws_retry=True)

    def test_listing_uses_shared_pagination(self):
        client = Mock()
        module = FakeModule({"id": None}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[{"Id": "delegation-1"}],
            ) as query,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["delegation_sets"], [{"id": "delegation-1"}])
        query.assert_called_once()

    def test_listing_requires_pagination_parameters(self):
        client = Mock()
        module = FakeModule({"id": None}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        require_methods.assert_called_once_with(
            module,
            client,
            "Route53",
            {"list_reusable_delegation_sets": ("Marker", "MaxItems")},
        )

    def test_get_rejects_malformed_or_wrong_delegation_set(self):
        responses = (
            None,
            {},
            {"DelegationSet": None},
            {"DelegationSet": {"Id": "delegation-2"}},
        )
        for response in responses:
            with self.subTest(response=response):
                client = Mock(get_reusable_delegation_set=Mock(return_value=response))
                module = FakeModule({"id": "delegation-1"}, client=client)
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    patch.object(plugin, "require_client_methods"),
                    self.assertRaises(ModuleFail),
                ):
                    plugin.main()

    def test_get_accepts_full_path_for_bare_response_id(self):
        client = Mock(get_reusable_delegation_set=Mock(return_value={"DelegationSet": {"Id": "delegation-1"}}))
        module = FakeModule({"id": "/delegationset/delegation-1"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["delegation_sets"], [{"id": "delegation-1"}])

    def test_listing_rejects_malformed_delegation_set(self):
        module = FakeModule({"id": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[None]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list AWS Route53 reusable delegation sets: AWS returned an invalid response",
        )
