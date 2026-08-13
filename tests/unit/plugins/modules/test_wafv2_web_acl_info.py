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
