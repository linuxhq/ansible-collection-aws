from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ssm_association_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class SsmAssociationInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["filters"]["type"] == "dict"

    def test_scalar_filters_are_converted_to_association_filters(self):
        module = FakeModule({"filters": {"Name": "document"}}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3]["list_associations"],
            ("AssociationFilterList",),
        )
        self.assertEqual(
            query.call_args.kwargs["AssociationFilterList"],
            [{"key": "Name", "value": "document"}],
        )
