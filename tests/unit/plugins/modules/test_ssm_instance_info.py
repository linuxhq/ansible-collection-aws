from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ssm_instance_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class SsmInstanceInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["ping_status"]["choices"] == [
            "ConnectionLost",
            "Inactive",
            "Online",
        ]

    def test_rejects_more_than_one_hundred_instance_ids(self):
        module = FakeModule(
            {
                "filters": None,
                "instance_ids": [f"i-{index}" for index in range(101)],
                "ping_status": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("at most 100", raised.exception.values["msg"])

    def test_rejects_empty_instance_id(self):
        module = FakeModule({"filters": None, "instance_ids": [""], "ping_status": None})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("empty entries", raised.exception.values["msg"])

    def test_instance_and_ping_filters_override_and_stringify_filters(self):
        module = FakeModule(
            {
                "filters": {"PlatformTypes": ["Linux"], "AgentVersion": 3},
                "instance_ids": ["i-1"],
                "ping_status": "Online",
            },
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(require.call_args.args[3], {"describe_instance_information": ("Filters",)})
        self.assertEqual(
            query.call_args.kwargs["Filters"],
            [
                {"Key": "PlatformTypes", "Values": ["Linux"]},
                {"Key": "AgentVersion", "Values": ["3"]},
                {"Key": "InstanceIds", "Values": ["i-1"]},
                {"Key": "PingStatus", "Values": ["Online"]},
            ],
        )

    def test_rejects_malformed_instance(self):
        module = FakeModule(
            {"filters": None, "instance_ids": None, "ping_status": None},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"InstanceId": "i-1"}, None]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while describing AWS Systems Manager instances; instance 1 was not a dictionary",
        )

    def test_rejects_malformed_instance_list(self):
        module = FakeModule(
            {"filters": None, "instance_ids": None, "ping_status": None},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while describing AWS Systems Manager instances; instance list was not a list",
        )

    def test_returns_ids_and_normalized_instances(self):
        module = FakeModule(
            {"filters": None, "instance_ids": None, "ping_status": None},
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[{"InstanceId": "i-1", "PingStatus": "Online"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["instance_ids"], ["i-1"])
        self.assertEqual(
            raised.exception.values["instances"],
            [{"instance_id": "i-1", "ping_status": "Online"}],
        )

    def test_warns_when_instance_id_is_invalid(self):
        module = FakeModule(
            {"filters": None, "instance_ids": None, "ping_status": None},
            client=Mock(),
        )
        module.warn = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"InstanceId": "i-1"}, {}]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["instance_ids"], ["i-1"])
        self.assertEqual(raised.exception.values["instances"], [{"instance_id": "i-1"}, {}])
        module.warn.assert_called_once_with(
            "Unexpected response while describing AWS Systems Manager instances; "
            "instance 1 did not contain a valid InstanceId and was omitted from instance_ids"
        )
