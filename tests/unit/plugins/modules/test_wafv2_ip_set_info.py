from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import wafv2_ip_set_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Wafv2IpSetInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["scope"]["choices"] == [
            "cloudfront",
            "regional",
        ]

    def test_cloudfront_scope_is_uppercase_for_aws(self):
        client = Mock()
        module = FakeModule({"id": None, "name": None, "scope": "cloudfront"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(query.call_args.kwargs["Scope"], "CLOUDFRONT")

    def test_rejects_empty_filters(self):
        for option in ("id", "name"):
            params = {"id": None, "name": None, "scope": "regional"}
            params[option] = ""
            with (
                self.subTest(option=option),
                patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params)),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.main()
            self.assertEqual(raised.exception.values["msg"], f"{option} must not be empty")

    def test_rejects_malformed_selected_summary(self):
        for summary, message in (
            (None, "Unexpected response while listing"),
            ({}, "invalid ID"),
            ({"Id": "id-1"}, "invalid name"),
        ):
            module = FakeModule({"id": None, "name": None, "scope": "regional"}, client=Mock())
            with (
                self.subTest(summary=summary),
                patch.object(plugin, "AnsibleAWSModule", return_value=module),
                patch.object(plugin, "require_client_methods"),
                patch.object(plugin, "query_list", return_value=[summary]),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.main()
            self.assertIn(message, raised.exception.values["msg"])

    def test_rejects_malformed_summary_list(self):
        module = FakeModule({"id": None, "name": None, "scope": "regional"}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while listing AWS WAFv2 IP sets for REGIONAL",
        )

    def test_filtered_lookup_skips_malformed_unmatched_summary(self):
        client = Mock(
            get_ip_set=Mock(
                return_value={
                    "IPSet": {
                        "Addresses": [],
                        "ARN": "arn:ip-set",
                        "Id": "wanted",
                        "IPAddressVersion": "IPV4",
                        "Name": "target",
                    }
                }
            )
        )
        module = FakeModule({"id": "wanted", "name": None, "scope": "regional"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[None, {"Id": "wanted", "Name": "target"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["ip_sets"][0]["id"], "wanted")

    def test_rejects_malformed_ip_set_response(self):
        client = Mock(get_ip_set=Mock(return_value={}))
        module = FakeModule({"id": None, "name": None, "scope": "regional"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"Id": "id-1", "Name": "name-1"}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS WAFv2 IP set name-1/id-1",
        )
