from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    global_accelerator_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class GlobalAcceleratorInfoTests(TestCase):
    def test_accelerator_disappearing_during_tag_lookup_is_omitted(self):
        client = Mock()
        client.describe_accelerator.return_value = {
            "Accelerator": {"AcceleratorArn": "arn:gone"}
        }
        client.list_tags_for_resource.side_effect = plugin.ClientError(
            {
                "Error": {
                    "Code": "AcceleratorNotFoundException",
                    "Message": "gone",
                }
            },
            "ListTagsForResource",
        )
        module = FakeModule(
            {
                "arn": "arn:gone",
                "include_endpoint_groups": False,
                "include_listeners": False,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["accelerators"], [])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["include_endpoint_groups"]["default"] is False

    def test_empty_results_defer_listener_methods(self):
        module = FakeModule(
            {"arn": None, "include_endpoint_groups": True, "include_listeners": False},
            client=Mock(),
        )
        require = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods", require),
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(require.call_count, 1)
        self.assertNotIn("list_listeners", require.call_args.args[3])
        self.assertNotIn("list_endpoint_groups", require.call_args.args[3])

    def test_empty_results_do_not_require_tag_lookup(self):
        module = FakeModule(
            {"arn": None, "include_endpoint_groups": False, "include_listeners": False},
            client=Mock(),
        )
        require = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods", require),
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(require.call_count, 1)
        self.assertNotIn("list_tags_for_resource", require.call_args.args[3])

    def test_endpoint_groups_are_nested_under_their_listener(self):
        client = Mock()
        client.describe_accelerator.return_value = {
            "Accelerator": {"AcceleratorArn": "arn:accelerator", "Name": "main"}
        }
        client.list_tags_for_resource.return_value = {"Tags": []}
        module = FakeModule(
            {
                "arn": "arn:accelerator",
                "include_endpoint_groups": True,
                "include_listeners": False,
            },
            client=client,
        )
        require = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods", require),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Listeners": [{"ListenerArn": "arn:listener"}]},
                    {"EndpointGroups": [{"EndpointGroupArn": "arn:endpoint-group"}]},
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        listener = raised.exception.values["accelerators"][0]["listeners"][0]
        self.assertEqual(listener["accelerator_arn"], "arn:accelerator")
        self.assertEqual(
            listener["endpoint_groups"][0]["endpoint_group_arn"],
            "arn:endpoint-group",
        )
        required_methods = {
            method for call in require.call_args_list for method in call.args[3]
        }
        self.assertIn("list_listeners", required_methods)
        self.assertIn("list_endpoint_groups", required_methods)
