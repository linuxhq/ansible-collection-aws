from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import wafv2_web_acl_logging as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Wafv2WebAclLoggingTests(TestCase):
    def test_absent_tolerates_configuration_disappearing_during_delete(self):
        client = Mock()
        client.delete_logging_configuration.side_effect = plugin.ClientError(
            {"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}},
            "DeleteLoggingConfiguration",
        )
        module = FakeModule({"resource_arn": "arn:web-acl"})
        with (
            patch.object(plugin, "get_logging_configuration", return_value={}),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_if"] == [("state", "present", ["log_destination_configs"])]

    def test_check_mode_returns_desired_logging_configuration(self):
        module = FakeModule(
            {
                "log_destination_configs": ["arn:log"],
                "resource_arn": "arn:web-acl",
            },
            check_mode=True,
        )
        with (
            patch.object(plugin, "get_logging_configuration", return_value=None),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["logging_configuration"]["log_destination_configs"],
            ["arn:log"],
        )

    def test_present_requires_exactly_one_logging_destination(self):
        for destinations in ([], ["arn:first", "arn:second"]):
            with self.subTest(destinations=destinations):
                module = FakeModule(
                    {
                        "log_destination_configs": destinations,
                        "resource_arn": "arn:web-acl",
                        "state": "present",
                    }
                )
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    plugin.main()

                self.assertIn("exactly 1", raised.exception.values["msg"])

    def test_rejects_empty_arns(self):
        for params, message in (
            (
                {
                    "log_destination_configs": ["arn:log"],
                    "resource_arn": "",
                    "state": "present",
                },
                "resource_arn must not be empty",
            ),
            (
                {
                    "log_destination_configs": [""],
                    "resource_arn": "arn:web-acl",
                    "state": "present",
                },
                "log_destination_configs must not contain empty entries",
            ),
        ):
            with (
                self.subTest(message=message),
                patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params)),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.main()

            self.assertEqual(raised.exception.values["msg"], message)

    def test_destination_update_preserves_unmanaged_logging_settings(self):
        client = Mock()
        current = {
            "LogDestinationConfigs": ["arn:old"],
            "LoggingFilter": {"DefaultBehavior": "KEEP", "Filters": []},
            "RedactedFields": [{"Method": {}}],
            "ResourceArn": "arn:web-acl",
        }
        client.put_logging_configuration.return_value = {
            "LoggingConfiguration": dict(current, LogDestinationConfigs=["arn:new"])
        }
        module = FakeModule(
            {
                "log_destination_configs": ["arn:new"],
                "resource_arn": "arn:web-acl",
            }
        )

        with (
            patch.object(plugin, "get_logging_configuration", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["logging_configuration"]["log_destination_configs"],
            ["arn:new"],
        )
        client.put_logging_configuration.assert_called_once_with(
            LoggingConfiguration={
                "LogDestinationConfigs": ["arn:new"],
                "LoggingFilter": {"DefaultBehavior": "KEEP", "Filters": []},
                "RedactedFields": [{"Method": {}}],
                "ResourceArn": "arn:web-acl",
            },
            aws_retry=True,
        )

    def test_get_rejects_malformed_response(self):
        for response in ([], {"LoggingConfiguration": []}):
            client = Mock()
            client.get_logging_configuration.return_value = response
            module = FakeModule({"resource_arn": "arn:web-acl"})

            with self.subTest(response=response), self.assertRaises(ModuleFail) as raised:
                plugin.get_logging_configuration(client, module)

            self.assertIn("unexpected logging configuration response", raised.exception.values["msg"])

    def test_put_rejects_malformed_response_and_reports_change(self):
        client = Mock()
        client.put_logging_configuration.return_value = []
        module = FakeModule(
            {
                "log_destination_configs": ["arn:new"],
                "resource_arn": "arn:web-acl",
            }
        )

        with (
            patch.object(plugin, "get_logging_configuration", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertIn("did not return the logging configuration", raised.exception.values["msg"])
