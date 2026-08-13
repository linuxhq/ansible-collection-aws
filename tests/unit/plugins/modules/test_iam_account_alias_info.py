from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import iam_account_alias_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class IamAccountAliasInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"] == {}

    def test_returns_aliases_from_query(self):
        module = FakeModule({}, client=Mock())
        require_client_methods = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods", require_client_methods),
            patch.object(plugin, "query_list", return_value=["main"]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(
            require_client_methods.call_args.args[3]["list_account_aliases"],
            ("Marker", "MaxItems"),
        )
        self.assertEqual(raised.exception.values["account_aliases"], ["main"])
