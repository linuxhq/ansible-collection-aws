from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import rds_subnet_group_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
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

    def test_malformed_response_fails_cleanly(self):
        for response in (None, {}, {"DBSubnetGroups": [None]}):
            with self.subTest(response=response):
                module = FakeModule({"filters": None, "name": None}, client=Mock())
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    patch.object(plugin, "require_client_methods"),
                    patch.object(plugin, "paginated_query_with_retries", return_value=response),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    plugin.main()

                self.assertEqual(
                    raised.exception.values["msg"],
                    "Unable to describe AWS RDS DB subnet groups: AWS returned an invalid response",
                )
