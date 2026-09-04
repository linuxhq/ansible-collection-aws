from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Route53ResolverInfoTests(TestCase):
    def test_malformed_endpoint_is_rejected(self):
        module = FakeModule({"filters": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"Arn": "arn:endpoint"}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("without a valid ID", raised.exception.values["msg"])

    def test_malformed_detail_response_is_rejected(self):
        module = FakeModule({"filters": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"Id": "rslvr-1"}]),
            patch.object(plugin, "paginated_query_with_retries", return_value=[]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "list_resolver_endpoint_ip_addresses: AWS returned an invalid response",
        )

    def test_malformed_ip_address_and_tag_are_rejected(self):
        module = FakeModule({"filters": None}, client=Mock())
        endpoint = {"Arn": "arn:endpoint", "Id": "rslvr-1"}
        cases = [
            ([{"Ip": "192.0.2.1"}], "without a subnet ID"),
            ([{"Key": "Name"}], "invalid tag"),
        ]
        for index, (items, message) in enumerate(cases):
            responses = (
                [{"IpAddresses": items}]
                if index == 0
                else [
                    {"IpAddresses": [{"SubnetId": "subnet-1"}]},
                    {"Tags": items},
                ]
            )
            with (
                self.subTest(message=message),
                patch.object(plugin, "AnsibleAWSModule", return_value=module),
                patch.object(plugin, "require_client_methods"),
                patch.object(plugin, "query_list", return_value=[endpoint]),
                patch.object(plugin, "paginated_query_with_retries", side_effect=responses),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.main()
            self.assertIn(message, raised.exception.values["msg"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["filters"]["type"] == "dict"

    def test_empty_endpoint_list_skips_detail_calls(self):
        module = FakeModule({"filters": None}, client=Mock())
        details = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]),
            patch.object(plugin, "paginated_query_with_retries", details),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        details.assert_not_called()
        self.assertEqual(raised.exception.values["resolver_endpoints"], [])

    def test_endpoints_are_enriched_with_ip_addresses_and_tags(self):
        module = FakeModule({"filters": None}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[{"Arn": "arn:endpoint", "Id": "rslvr-1"}],
            ),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"IpAddresses": [{"Ip": "192.0.2.1", "SubnetId": "subnet-1"}]},
                    {"Tags": [{"Key": "Name", "Value": "main"}]},
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        endpoint = raised.exception.values["resolver_endpoints"][0]
        self.assertEqual(endpoint["ip_addresses"][0]["ip"], "192.0.2.1")
        self.assertEqual(endpoint["tags"], {"Name": "main"})
