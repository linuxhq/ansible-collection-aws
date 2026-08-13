from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import account_region as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class AccountRegionTests(TestCase):
    def test_sdk_validation_requires_region_name(self):
        for state in ("present", "absent"):
            with self.subTest(state=state):
                module = Mock(
                    params={
                        "name": "af-south-1",
                        "state": state,
                        "wait": False,
                        "wait_delay": 30,
                        "wait_timeout": 1800,
                    },
                    client=Mock(return_value=Mock()),
                )
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    patch.object(plugin, "require_client_methods") as require,
                    patch.object(plugin, f"ensure_{state}"),
                ):
                    plugin.main()

                methods = require.call_args.args[3]
                self.assertEqual(methods, {"get_region_opt_status": ("RegionName",)})

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["wait_timeout"]["default"] == 1800

    def test_check_mode_predicts_region_enablement(self):
        module = FakeModule({"name": "af-south-1", "wait": True}, check_mode=True)
        client = Mock()
        with (
            patch.object(plugin, "get_region_opt_status", return_value="DISABLED"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        client.enable_region.assert_not_called()
        self.assertEqual(raised.exception.values["region_opt_status"], "ENABLED")
        self.assertTrue(raised.exception.values["changed"])

    def test_default_region_cannot_be_disabled(self):
        module = FakeModule({"name": "us-east-1", "wait": True})
        with (
            patch.object(
                plugin,
                "get_region_opt_status",
                return_value="ENABLED_BY_DEFAULT",
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_absent(Mock(), module)

        self.assertIn("default Regions cannot be disabled", raised.exception.values["msg"])

    def test_enable_waits_for_disabling_region_even_without_final_wait(self):
        module = FakeModule({"name": "af-south-1", "wait": False})
        client = Mock()
        with (
            patch.object(
                plugin,
                "get_region_opt_status",
                side_effect=["DISABLING", "ENABLING"],
            ),
            patch.object(plugin, "wait_for_status") as wait_for_status,
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)
        wait_for_status.assert_called_once_with(client, module, "region_disabled", plugin.ABSENT_STEADY_STATUSES)
        client.enable_region.assert_called_once_with(RegionName="af-south-1", aws_retry=True)
        self.assertEqual(require.call_args.args[3], {"enable_region": ("RegionName",)})

    def test_disable_waits_for_enabling_region_even_without_final_wait(self):
        module = FakeModule({"name": "af-south-1", "wait": False})
        client = Mock()
        with (
            patch.object(
                plugin,
                "get_region_opt_status",
                side_effect=["ENABLING", "DISABLING"],
            ),
            patch.object(plugin, "wait_for_status") as wait_for_status,
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_absent(client, module)
        wait_for_status.assert_called_once_with(client, module, "region_enabled", plugin.PRESENT_STEADY_STATUSES)
        client.disable_region.assert_called_once_with(RegionName="af-south-1", aws_retry=True)
        self.assertEqual(require.call_args.args[3], {"disable_region": ("RegionName",)})
