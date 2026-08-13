from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    ec2_vpc_prefix_list_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class Ec2VpcPrefixListInfoTests(TestCase):
    def test_prefix_list_disappearing_during_entry_lookup_is_omitted(self):
        client = Mock()
        module = FakeModule(
            {"filters": None, "prefix_list_ids": ["pl-gone"], "target_version": None},
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(
                plugin,
                "query_list",
                return_value=[{"PrefixListId": "pl-gone"}],
            ),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=plugin.ClientError(
                    {
                        "Error": {
                            "Code": "InvalidPrefixListID.NotFound",
                            "Message": "gone",
                        }
                    },
                    "GetManagedPrefixListEntries",
                ),
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["prefix_lists"], [])
        self.assertEqual(
            require_methods.call_args_list[0].args,
            (
                module,
                client,
                "EC2",
                {
                    "describe_managed_prefix_lists": (
                        "PrefixListIds",
                        "MaxResults",
                        "NextToken",
                    ),
                },
            ),
        )
        self.assertEqual(
            require_methods.call_args_list[1].args,
            (
                module,
                client,
                "EC2",
                {
                    "get_managed_prefix_list_entries": (
                        "MaxResults",
                        "NextToken",
                        "PrefixListId",
                    ),
                },
            ),
        )

    def test_sdk_validation_ignores_unused_filters(self):
        module = FakeModule(
            {"filters": None, "prefix_list_ids": None, "target_version": None},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(
            require_methods.call_args.args[3]["describe_managed_prefix_lists"],
            ("MaxResults", "NextToken"),
        )
        self.assertEqual(require_methods.call_count, 1)

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["target_version"]["type"] == "int"

    def test_target_version_is_used_for_entries(self):
        module = FakeModule(
            {
                "filters": None,
                "prefix_list_ids": ["pl-1", "pl-1"],
                "target_version": 2,
            },
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[{"PrefixListId": "pl-1", "PrefixListName": "main"}],
            ) as query,
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"Entries": []},
            ) as entries,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(query.call_args.kwargs["PrefixListIds"], ["pl-1"])
        self.assertEqual(entries.call_args.kwargs["TargetVersion"], 2)
