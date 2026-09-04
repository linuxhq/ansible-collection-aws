from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_serial_console_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Ec2SerialConsoleInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"] == {}

    def test_response_metadata_is_removed(self):
        client = Mock(
            get_serial_console_access_status=Mock(
                return_value={
                    "SerialConsoleAccessEnabled": True,
                    "ResponseMetadata": {"RequestId": "request"},
                }
            )
        )
        module = FakeModule({}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["serial_console_access"],
            {"serial_console_access_enabled": True},
        )

    def test_rejects_invalid_serial_console_status(self):
        client = Mock(get_serial_console_access_status=Mock(return_value={}))
        module = FakeModule({}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("invalid serial console access status", raised.exception.values["msg"])
