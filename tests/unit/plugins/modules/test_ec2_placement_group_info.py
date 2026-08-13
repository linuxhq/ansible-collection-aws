from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_placement_group_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class Ec2PlacementGroupInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["group_ids"]["elements"] == "str"

    def test_group_ids_are_sent_with_retry(self):
        client = Mock()
        module = FakeModule(
            {
                "filters": None,
                "group_ids": ["pg-1", "pg-1"],
                "group_names": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]) as query_list,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3],
            {"describe_placement_groups": ("GroupIds",)},
        )
        query_list.assert_called_once_with(
            module,
            client,
            "describe_placement_groups",
            "PlacementGroups",
            "Unable to describe EC2 placement groups",
            GroupIds=["pg-1"],
        )
