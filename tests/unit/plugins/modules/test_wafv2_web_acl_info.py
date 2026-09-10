from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import wafv2_web_acl_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Wafv2WebAclInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["scope"]["choices"] == [
            "cloudfront",
            "regional",
        ]

    def test_regional_scope_is_uppercase_for_aws(self):
        client = Mock()
        module = FakeModule({"id": None, "name": None, "scope": "regional"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(query.call_args.kwargs["Scope"], "REGIONAL")

    def test_byte_values_are_returned_as_json_safe_text(self):
        client = Mock()
        client.get_web_acl.return_value = {
            "WebACL": {
                "CustomResponseBodies": {"body": {"Content": bytearray(b"hello")}},
                "Id": "acl-1",
                "Name": "main",
            }
        }
        module = FakeModule({"id": "acl-1", "name": None, "scope": "regional"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[{"Id": "acl-1", "Name": "main"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["web_acls"][0]["custom_response_bodies"]["body"]["content"],
            "hello",
        )

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

    def test_rejects_malformed_summary_list(self):
        module = FakeModule({"id": None, "name": None, "scope": "regional"}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("Unexpected response while listing", raised.exception.values["msg"])

    def test_rejects_malformed_selected_summary(self):
        for summary, message in (
            (None, "Unexpected response while listing"),
            ({}, "invalid ID"),
            ({"Id": "acl-1"}, "invalid name"),
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

    def test_filtered_lookup_skips_malformed_unmatched_summary(self):
        client = Mock(
            get_web_acl=Mock(
                return_value={
                    "WebACL": {
                        "ARN": "arn:web-acl",
                        "DefaultAction": {"Allow": {}},
                        "Id": "wanted",
                        "Name": "target",
                        "VisibilityConfig": {},
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

        self.assertEqual(raised.exception.values["web_acls"][0]["id"], "wanted")

    def test_rejects_malformed_web_acl_response(self):
        client = Mock(get_web_acl=Mock(return_value={}))
        module = FakeModule({"id": None, "name": None, "scope": "regional"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"Id": "acl-1", "Name": "main"}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS WAFv2 web ACL main/acl-1",
        )
