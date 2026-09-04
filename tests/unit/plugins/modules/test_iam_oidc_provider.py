from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, call, patch

from ansible_collections.linuxhq.aws.plugins.modules import iam_oidc_provider as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class IamOidcProviderTests(TestCase):
    def test_absent_tolerates_provider_disappearing_during_delete(self):
        client = Mock()
        client.delete_open_id_connect_provider.side_effect = plugin.ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "gone"}},
            "DeleteOpenIDConnectProvider",
        )
        module = FakeModule({"url": "https://example.com/id"})
        current = {"OpenIDConnectProviderArn": "arn:provider"}
        with (
            patch.object(plugin, "get_provider_by_url", return_value=current),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_if"] == [("state", "present", ["client_id_list", "thumbprint_list"])]
        assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]

    def test_main_only_requires_provider_listing_before_reconciliation(self):
        module = Mock(
            params={
                "client_id_list": ["client"],
                "state": "present",
                "tags": None,
                "thumbprint_list": ["a" * 40],
                "url": "https://example.com/id",
            },
            client=Mock(return_value=Mock()),
        )
        require_client_methods = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "ensure_present"),
            patch.object(plugin, "require_client_methods", require_client_methods),
        ):
            plugin.main()

        require_client_methods.assert_called_once_with(
            module,
            module.client.return_value,
            "IAM",
            {"list_open_id_connect_providers": ()},
        )

    def test_provider_lookup_normalizes_url(self):
        client = Mock()
        module = SimpleNamespace(params={"url": "https://EXAMPLE.com/id"})
        provider = {
            "OpenIDConnectProviderArn": "arn:aws:iam::1:oidc-provider/example.com/id",
            "Url": "example.com/id",
        }
        providers = [{"Arn": "arn:aws:iam::1:oidc-provider/example.com/id"}]
        with (
            patch.object(plugin, "query_list", return_value=providers) as query_list,
            patch.object(plugin, "get_provider_by_arn", return_value=provider),
            patch.object(plugin, "require_client_methods"),
        ):
            result = plugin.get_provider_by_url(client, module)
        self.assertEqual(result, provider)
        query_list.assert_called_once_with(
            module,
            client,
            "list_open_id_connect_providers",
            "OpenIDConnectProviderList",
            "Unable to list AWS IAM OIDC providers",
        )

    def test_provider_lookup_rejects_invalid_summaries(self):
        module = FakeModule({"url": "https://example.com/id"})
        with (
            patch.object(plugin, "query_list", return_value=[{}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.get_provider_by_url(Mock(), module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list AWS IAM OIDC providers: AWS returned an invalid response",
        )

    def test_non_hexadecimal_thumbprint_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "client_id_list": ["client"],
                "state": "present",
                "tags": None,
                "thumbprint_list": ["z" * 40],
                "url": "https://example.com/id",
            },
            ("thumbprint_list entries must be exactly 40 hexadecimal " f"characters: {'z' * 40}"),
        )

    def test_present_rejects_non_https_url(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "client_id_list": [],
                "state": "present",
                "tags": None,
                "thumbprint_list": [],
                "url": "http://example.com/id",
            },
            "url must begin with https://",
        )

    def test_present_rejects_url_without_host(self):
        for url in ("https://", "https:///path"):
            with self.subTest(url=url):
                assert_module_rejects(
                    self,
                    plugin,
                    {
                        "client_id_list": ["client"],
                        "state": "present",
                        "tags": None,
                        "thumbprint_list": ["a" * 40],
                        "url": url,
                    },
                    "url must identify an OIDC provider host",
                )

    def test_provider_list_limits_are_rejected(self):
        cases = [
            (
                {
                    "client_id_list": [str(index) for index in range(101)],
                    "state": "present",
                    "tags": None,
                    "thumbprint_list": ["a" * 40],
                    "url": "https://example.com/id",
                },
                "client_id_list must contain at most 100 unique entries",
            ),
            (
                {
                    "client_id_list": ["client"],
                    "state": "present",
                    "tags": None,
                    "thumbprint_list": [f"{index:040x}" for index in range(6)],
                    "url": "https://example.com/id",
                },
                "thumbprint_list must contain at most 5 unique entries",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_thumbprint_case_does_not_trigger_an_update(self):
        client = Mock()
        module = FakeModule(
            {
                "client_id_list": [],
                "purge_tags": True,
                "tags": None,
                "thumbprint_list": ["A" * 40],
                "url": "https://example.com/id",
            }
        )
        current = {
            "ClientIDList": [],
            "OpenIDConnectProviderArn": "arn:provider",
            "ThumbprintList": ["a" * 40],
            "Url": "example.com/id",
        }
        with (
            patch.object(plugin, "get_provider_by_url", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertFalse(raised.exception.values["changed"])
        client.update_open_id_connect_provider_thumbprint.assert_not_called()

    def test_existing_provider_reconciles_client_ids_and_thumbprints(self):
        client = Mock()
        module = FakeModule(
            {
                "client_id_list": ["keep", "new"],
                "purge_tags": True,
                "tags": None,
                "thumbprint_list": ["new-thumbprint"],
                "url": "https://example.com/id",
            }
        )
        current = {
            "ClientIDList": ["keep", "old"],
            "OpenIDConnectProviderArn": "arn:provider",
            "ThumbprintList": ["old-thumbprint"],
            "Url": "example.com/id",
        }
        with (
            patch.object(plugin, "get_provider_by_url", return_value=current),
            patch.object(plugin, "get_provider_by_arn") as get_provider_by_arn,
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["open_id_connect_provider"]["client_id_list"],
            ["keep", "new"],
        )
        self.assertEqual(
            raised.exception.values["open_id_connect_provider"]["thumbprint_list"],
            ["new-thumbprint"],
        )
        get_provider_by_arn.assert_not_called()
        client.remove_client_id_from_open_id_connect_provider.assert_called_once_with(
            OpenIDConnectProviderArn="arn:provider",
            ClientID="old",
            aws_retry=True,
        )
        client.add_client_id_to_open_id_connect_provider.assert_called_once_with(
            OpenIDConnectProviderArn="arn:provider",
            ClientID="new",
            aws_retry=True,
        )
        self.assertLess(
            client.method_calls.index(
                call.add_client_id_to_open_id_connect_provider(
                    OpenIDConnectProviderArn="arn:provider",
                    ClientID="new",
                    aws_retry=True,
                )
            ),
            client.method_calls.index(
                call.remove_client_id_from_open_id_connect_provider(
                    OpenIDConnectProviderArn="arn:provider",
                    ClientID="old",
                    aws_retry=True,
                )
            ),
        )
        client.update_open_id_connect_provider_thumbprint.assert_called_once_with(
            OpenIDConnectProviderArn="arn:provider",
            ThumbprintList=["new-thumbprint"],
            aws_retry=True,
        )

    def test_new_provider_request_deduplicates_ids_and_includes_tags(self):
        client = Mock()
        client.create_open_id_connect_provider.return_value = {"OpenIDConnectProviderArn": "arn:provider"}
        module = FakeModule(
            {
                "client_id_list": ["client-b", "client-a", "client-a"],
                "purge_tags": True,
                "tags": {"Name": "main"},
                "thumbprint_list": ["thumbprint", "thumbprint"],
                "url": "https://example.com/id",
            }
        )
        with (
            patch.object(plugin, "get_provider_by_url", return_value=None),
            patch.object(plugin, "get_provider_by_arn", return_value=None),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["open_id_connect_provider"],
            {
                "client_id_list": ["client-a", "client-b"],
                "open_id_connect_provider_arn": "arn:provider",
                "tags": {"Name": "main"},
                "thumbprint_list": ["thumbprint"],
                "url": "example.com/id",
            },
        )
        client.create_open_id_connect_provider.assert_called_once_with(
            ClientIDList=["client-a", "client-b"],
            Tags=[{"Key": "Name", "Value": "main"}],
            ThumbprintList=["thumbprint"],
            Url="https://example.com/id",
            aws_retry=True,
        )

    def test_present_rejects_empty_provider_lists(self):
        cases = [
            ([], ["a" * 40], "client_id_list must contain at least 1 entry"),
            (["client"], [], "thumbprint_list must contain at least 1 entry"),
        ]
        for client_ids, thumbprints, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(
                    self,
                    plugin,
                    {
                        "client_id_list": client_ids,
                        "state": "present",
                        "tags": None,
                        "thumbprint_list": thumbprints,
                        "url": "https://example.com/id",
                    },
                    message,
                )
