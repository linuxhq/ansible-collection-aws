from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_serial_console as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class Ec2SerialConsoleTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["state"]["choices"] == ["absent", "present"]

    def test_response_metadata_is_not_returned(self):
        response = {"SerialConsoleAccessEnabled": True, "ResponseMetadata": {"x": 1}}
        assert plugin.normalized_serial_console_access(response) == {"serial_console_access_enabled": True}

    def test_check_mode_projects_enabled_state_without_mutation(self):
        client = Mock()
        client.get_serial_console_access_status.return_value = {"SerialConsoleAccessEnabled": False}
        module = FakeModule({"state": "present"}, check_mode=True, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertTrue(raised.exception.values["changed"])
        self.assertTrue(raised.exception.values["serial_console_access"]["serial_console_access_enabled"])
        client.enable_serial_console_access.assert_not_called()
        self.assertEqual(require.call_count, 1)
        self.assertEqual(require.call_args.args[3], {"get_serial_console_access_status": ()})
