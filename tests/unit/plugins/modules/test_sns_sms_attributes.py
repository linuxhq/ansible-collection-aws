from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import sns_sms_attributes as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class SnsSmsAttributesTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["default_sms_type"]["choices"] == [
            "Promotional",
            "Transactional",
        ]

    def test_rejects_sampling_rate_above_percent(self):
        module = FakeModule({"delivery_status_success_sampling_rate": 101})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("between 0 and 100", raised.exception.values["msg"])

    def test_partial_update_preserves_unmanaged_attributes(self):
        client = Mock()
        client.get_sms_attributes.return_value = {
            "attributes": {
                "DefaultSenderID": "old",
                "MonthlySpendLimit": "100",
            }
        }
        params = dict.fromkeys(plugin.MANAGED_ATTRIBUTES)
        params["default_sender_id"] = "new"
        module = FakeModule(params, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        client.set_sms_attributes.assert_called_once_with(attributes={"DefaultSenderID": "new"}, aws_retry=True)
        self.assertEqual(raised.exception.values["attributes"]["monthly_spend_limit"], "100")

    def test_report_only_mode_does_not_require_set_method(self):
        client = Mock()
        client.get_sms_attributes.return_value = {"attributes": {}}
        module = FakeModule(dict.fromkeys(plugin.MANAGED_ATTRIBUTES), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_methods.assert_called_once_with(module, client, "SNS", {"get_sms_attributes": ()})
        client.set_sms_attributes.assert_not_called()
