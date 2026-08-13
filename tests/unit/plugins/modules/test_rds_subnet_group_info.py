from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import rds_subnet_group_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class RdsSubnetGroupInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["name"]["type"] == "str"

    def test_name_is_forwarded_to_rds(self):
        module = FakeModule({"filters": None, "name": "main"}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"DBSubnetGroups": []},
            ) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3],
            {
                "describe_db_subnet_groups": (
                    "DBSubnetGroupName",
                    "Marker",
                    "MaxRecords",
                )
            },
        )
        self.assertEqual(query.call_args.kwargs["DBSubnetGroupName"], "main")
