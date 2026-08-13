from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ssm_send_command as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class SsmSendCommandTests(TestCase):
    def test_equivalent_targets_are_sent_once(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(
            {
                "comment": None,
                "document_name": "AWS-RunShellScript",
                "instance_ids": None,
                "max_concurrency": None,
                "max_errors": None,
                "parameters": {},
                "targets": [
                    {"key": "tag:Role", "values": ["web", "web"]},
                    {"key": "tag:Role", "values": ["web"]},
                ],
                "timeout_seconds": None,
                "wait": False,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            client.send_command.call_args.kwargs["Targets"],
            [{"Key": "tag:Role", "Values": ["web"]}],
        )

    def test_module_contract(self):
        assert_module_contract(self, plugin)

    def test_command_normalization_preserves_nested_request_keys(self):
        self.assertEqual(
            plugin.normalize_command(
                {
                    "CommandId": "command-1",
                    "Parameters": {"commands": ["echo test"]},
                    "Status": "Success",
                    "Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
                }
            ),
            {
                "command_id": "command-1",
                "parameters": {"commands": ["echo test"]},
                "status": "Success",
                "targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
            },
        )

    def test_provider_limits_are_rejected(self):
        cases = [
            (
                {"timeout_seconds": 29, "instance_ids": [], "targets": []},
                "timeout_seconds must be between 30 and 2592000",
            ),
            (
                {
                    "timeout_seconds": None,
                    "instance_ids": [f"i-{index}" for index in range(51)],
                    "targets": [],
                },
                "instance_ids must contain at most 50 entries",
            ),
            (
                {
                    "timeout_seconds": None,
                    "instance_ids": [""],
                    "targets": [],
                },
                "instance_ids must not contain empty entries",
            ),
            (
                {
                    "timeout_seconds": None,
                    "instance_ids": [],
                    "targets": [
                        {
                            "key": "InstanceIds",
                            "values": [f"i-{index}" for index in range(51)],
                        }
                    ],
                },
                "targets[].values must contain at most 50 entries",
            ),
            (
                {
                    "timeout_seconds": None,
                    "instance_ids": [],
                    "targets": [{"key": f"tag:Role{index}", "values": [f"i-{index}"]} for index in range(6)],
                },
                "targets must contain at most 5 entries",
            ),
            (
                {"timeout_seconds": None, "instance_ids": [], "targets": []},
                "instance_ids or targets must contain at least one entry",
            ),
            (
                {
                    "timeout_seconds": None,
                    "instance_ids": [],
                    "targets": [{"key": "", "values": ["i-1"]}],
                },
                "targets[].key must be 1 to 163 characters",
            ),
            (
                {
                    "timeout_seconds": None,
                    "instance_ids": [],
                    "targets": [{"key": "InstanceIds", "values": []}],
                },
                "targets[].values must contain at least one entry",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_wait_returns_terminal_command_and_invocations(self):
        client = Mock()
        client.send_command.return_value = {"Command": {"CommandId": "command-1", "Status": "Pending"}}
        module = FakeModule(
            {
                "comment": None,
                "document_name": "AWS-RunShellScript",
                "instance_ids": ["i-1", "i-1"],
                "max_concurrency": None,
                "max_errors": None,
                "parameters": {"commands": ["true"]},
                "targets": None,
                "timeout_seconds": None,
                "wait": True,
                "wait_delay": 1,
                "wait_timeout": 10,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                    {"CommandInvocations": [{"InstanceId": "i-1", "Status": "Success"}]},
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["status"], "Success")
        self.assertEqual(
            raised.exception.values["command_invocations"],
            [{"instance_id": "i-1", "status": "Success"}],
        )
        self.assertEqual(client.send_command.call_args.kwargs["InstanceIds"], ["i-1"])
        self.assertNotIn("Targets", client.send_command.call_args.kwargs)

    def test_wait_retries_empty_invocations_when_targets_exist(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(
            {
                "comment": None,
                "document_name": "AWS-RunShellScript",
                "instance_ids": ["i-1"],
                "max_concurrency": None,
                "max_errors": None,
                "parameters": {},
                "targets": None,
                "timeout_seconds": None,
                "wait": True,
                "wait_delay": 1,
                "wait_timeout": 10,
            },
            client=client,
        )
        command = {
            "CommandId": "command-1",
            "Status": "Success",
            "TargetCount": 1,
        }
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin.time, "monotonic", side_effect=[0, 1, 2, 3]),
            patch.object(plugin.time, "sleep"),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [command]},
                    {"CommandInvocations": []},
                    {"Commands": [command]},
                    {"CommandInvocations": [{"InstanceId": "i-1", "Status": "Success"}]},
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["command_invocations"],
            [{"instance_id": "i-1", "status": "Success"}],
        )

    def test_wait_retries_when_an_invocation_has_no_status(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(
            {
                "comment": None,
                "document_name": "AWS-RunShellScript",
                "instance_ids": ["i-1", "i-2"],
                "max_concurrency": None,
                "max_errors": None,
                "parameters": {},
                "targets": None,
                "timeout_seconds": None,
                "wait": True,
                "wait_delay": 1,
                "wait_timeout": 10,
            },
            client=client,
        )
        command = {"CommandId": "command-1", "Status": "Success", "TargetCount": 2}
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin.time, "monotonic", side_effect=[0, 1, 2, 3]),
            patch.object(plugin.time, "sleep"),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [command]},
                    {
                        "CommandInvocations": [
                            {"InstanceId": "i-1", "Status": "Success"},
                            {"InstanceId": "i-2"},
                        ]
                    },
                    {"Commands": [command]},
                    {
                        "CommandInvocations": [
                            {"InstanceId": "i-1", "Status": "Success"},
                            {"InstanceId": "i-2", "Status": "Success"},
                        ]
                    },
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(len(raised.exception.values["command_invocations"]), 2)

    def test_wait_retries_until_terminal_target_count_is_known(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(
            {
                "comment": None,
                "document_name": "AWS-RunShellScript",
                "instance_ids": ["i-1"],
                "max_concurrency": None,
                "max_errors": None,
                "parameters": {},
                "targets": None,
                "timeout_seconds": None,
                "wait": True,
                "wait_delay": 1,
                "wait_timeout": 10,
            },
            client=client,
        )
        module.warn = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin.time, "monotonic", side_effect=[0, 1, 2, 3]),
            patch.object(plugin.time, "sleep"),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                    {"CommandInvocations": []},
                    {
                        "Commands": [
                            {
                                "CommandId": "command-1",
                                "Status": "Success",
                                "TargetCount": 0,
                            }
                        ]
                    },
                    {"CommandInvocations": []},
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["command"]["target_count"], 0)
        module.warn.assert_called_once()

    def test_failed_command_is_not_hidden_by_successful_invocations(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(
            {
                "comment": None,
                "document_name": "AWS-RunShellScript",
                "instance_ids": ["i-1"],
                "max_concurrency": None,
                "max_errors": None,
                "parameters": {},
                "targets": None,
                "timeout_seconds": None,
                "wait": True,
                "wait_delay": 1,
                "wait_timeout": 10,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Failed"}]},
                    {"CommandInvocations": [{"Status": "Success"}]},
                ],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["status"], "Failed")
