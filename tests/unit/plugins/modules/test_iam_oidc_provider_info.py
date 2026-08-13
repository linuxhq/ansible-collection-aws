from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import iam_oidc_provider_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class IamOidcProviderInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["mutually_exclusive"] == [["arn", "url"]]

    def test_provider_listing_ignores_missing_arns(self):
        client = Mock()
        module = Mock()
        providers = [{}, {"Arn": "arn:provider"}]
        with patch.object(plugin, "query_list", return_value=providers) as query_list:
            assert plugin.list_provider_arns(client, module) == ["arn:provider"]
        query_list.assert_called_once_with(
            module,
            client,
            "list_open_id_connect_providers",
            "OpenIDConnectProviderList",
            "Unable to list AWS IAM OIDC providers",
        )

    def test_empty_listing_does_not_require_provider_get(self):
        client = Mock()
        module = FakeModule({"arn": None, "url": None}, client=client)
        require_client_methods = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "list_provider_arns", return_value=[]),
            patch.object(plugin, "require_client_methods", require_client_methods),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_client_methods.assert_called_once_with(
            module,
            client,
            "IAM",
            {"list_open_id_connect_providers": ()},
        )

    def test_url_filter_normalizes_scheme_and_ignores_other_arns(self):
        module = FakeModule({"arn": None, "url": "https://example.com/id"}, client=Mock())
        provider = {
            "OpenIDConnectProviderArn": "arn:aws:iam::1:oidc-provider/example.com/id",
            "Url": "example.com/id",
        }
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "list_provider_arns",
                return_value=[
                    "arn:aws:iam::1:oidc-provider/other.example.com",
                    "arn:aws:iam::1:oidc-provider/EXAMPLE.com/id",
                ],
            ),
            patch.object(plugin, "get_provider_by_arn", return_value=provider) as get,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["open_id_connect_providers"][0]["url"],
            "example.com/id",
        )
        get.assert_called_once()
