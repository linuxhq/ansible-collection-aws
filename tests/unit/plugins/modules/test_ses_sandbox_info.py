from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ses_sandbox_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class SesSandboxInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"] == {}

    def test_returns_account_details(self):
        module = FakeModule({}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "get_account", return_value={"production_access_enabled": True}),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertTrue(raised.exception.values["account"]["production_access_enabled"])
