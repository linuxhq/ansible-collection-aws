from types import SimpleNamespace
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


def send_params(**overrides):
    params = {
        "comment": None,
        "document_name": "AWS-RunShellScript",
        "instance_ids": ["i-1"],
        "max_concurrency": None,
        "max_errors": None,
        "parameters": {},
        "targets": None,
        "timeout_seconds": None,
        "wait": False,
        "wait_delay": 1,
        "wait_timeout": 10,
    }
    params.update(overrides)
    return params


def patch_time(*monotonic_values):
    mocked_time = SimpleNamespace(
        monotonic=Mock(side_effect=monotonic_values),
        sleep=Mock(),
    )
    return patch.object(plugin, "time", mocked_time)


class SsmSendCommandTests(TestCase):
    def test_equivalent_targets_are_sent_once(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(
            send_params(
                instance_ids=None,
                targets=[
                    {"key": "tag:Role", "values": ["web", "web"]},
                    {"key": "tag:Role", "values": ["web"]},
                ],
            ),
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

    def test_command_normalization_preserves_compatible_request_keys(self):
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
                {"document_name": "", "timeout_seconds": None, "instance_ids": ["i-1"], "targets": []},
                "document_name must not be empty",
            ),
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
                assert_module_rejects(self, plugin, send_params(**params), message)

    def test_wait_returns_terminal_command_and_invocations(self):
        client = Mock()
        client.send_command.return_value = {"Command": {"CommandId": "command-1", "Status": "Pending"}}
        module = FakeModule(
            send_params(instance_ids=["i-1", "i-1"], parameters={"commands": ["true"]}, wait=True),
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch_time(0, 1),
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
        module = FakeModule(send_params(wait=True), client=client)
        command = {
            "CommandId": "command-1",
            "Status": "Success",
            "TargetCount": 1,
        }
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch_time(0, 1, 2, 3),
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
        module = FakeModule(send_params(instance_ids=["i-1", "i-2"], wait=True), client=client)
        command = {"CommandId": "command-1", "Status": "Success", "TargetCount": 2}
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch_time(0, 1, 2, 3),
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
        module = FakeModule(send_params(wait=True), client=client)
        module.warn = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch_time(0, 1, 2, 3),
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
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch_time(0, 1),
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

    def test_check_mode_checks_client_capabilities_without_sending(self):
        client = Mock()
        module = FakeModule(send_params(), check_mode=True, client=client)
        module.client = Mock(return_value=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertTrue(raised.exception.values["changed"])
        module.client.assert_called_once()
        require.assert_called_once()
        client.send_command.assert_not_called()

    def test_client_methods_are_checked_before_sending(self):
        calls = []
        client = Mock(
            send_command=Mock(
                side_effect=lambda **kwargs: calls.append("send_command")
                or {"Command": {"CommandId": "command-1", "Status": "Pending"}}
            )
        )
        module = FakeModule(send_params(), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(
                plugin,
                "require_client_methods",
                side_effect=lambda *args, **kwargs: calls.append("require_client_methods"),
            ),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(calls, ["require_client_methods", "send_command"])

    def test_rejects_malformed_send_response(self):
        for response in (None, {"Command": None}):
            with self.subTest(response=response):
                client = Mock(send_command=Mock(return_value=response))
                module = FakeModule(send_params(), client=client)
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    patch.object(plugin, "require_positive_wait_bounds"),
                    patch.object(plugin, "require_client_methods"),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    plugin.main()
                self.assertEqual(
                    raised.exception.values["msg"],
                    "Unexpected response while sending AWS Systems Manager command using AWS-RunShellScript",
                )

    def test_rejects_missing_command_id(self):
        client = Mock(send_command=Mock(return_value={}))
        module = FakeModule(send_params(), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager did not return an ID for the command using AWS-RunShellScript",
        )

    def test_rejects_non_string_command_id(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": 1}}))
        module = FakeModule(send_params(), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager did not return an ID for the command using AWS-RunShellScript",
        )

    def test_rejects_malformed_initial_command_status(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1", "Status": []}}))
        module = FakeModule(send_params(), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager command command-1 did not return a valid status",
        )
        self.assertEqual(raised.exception.values["command"], {"command_id": "command-1", "status": []})
        self.assertEqual(raised.exception.values["command_id"], "command-1")
        self.assertEqual(raised.exception.values["status"], [])
        self.assertTrue(raised.exception.values["changed"])

    def test_rejects_malformed_wait_response(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[{"Commands": [None]}, {"CommandInvocations": []}],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS Systems Manager command command-1; "
            "command 0 was not a dictionary",
        )

    def test_rejects_malformed_commands_response(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[None, {"CommandInvocations": []}],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS Systems Manager command command-1; Commands was not a list",
        )

    def test_timeout_before_first_poll_returns_empty_invocations(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 11),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["command_invocations"], [])
        self.assertIsNone(raised.exception.values["status"])
        self.assertEqual(
            raised.exception.values["msg"],
            "Timed out waiting for AWS Systems Manager command command-1",
        )

    def test_wait_sleep_is_bounded_by_remaining_timeout(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True, wait_delay=5, wait_timeout=10), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 9, 9.75, 10) as mocked_time,
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Pending"}]},
                    {"CommandInvocations": []},
                ],
            ),
            self.assertRaises(ModuleFail),
        ):
            plugin.main()
        mocked_time.sleep.assert_called_once_with(0.25)

    def test_rejects_malformed_command_status(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": []}]},
                    {"CommandInvocations": []},
                ],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager command command-1 was returned by list_commands with an invalid status",
        )
        self.assertEqual(raised.exception.values["command_id"], "command-1")
        self.assertEqual(raised.exception.values["command_invocations"], [])
        self.assertEqual(raised.exception.values["status"], [])

    def test_wait_retries_when_command_has_no_status(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1, 2, 3),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1"}]},
                    {"CommandInvocations": []},
                    {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                    {"CommandInvocations": [{"Status": "Success"}]},
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["status"], "Success")

    def test_rejects_malformed_invocations_response(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[{"Commands": [{"CommandId": "command-1", "Status": "Success"}]}, None],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS Systems Manager command command-1; "
            "CommandInvocations was not a list",
        )

    def test_rejects_malformed_invocation_elements(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                    {"CommandInvocations": [None]},
                ],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS Systems Manager command command-1; "
            "invocation 0 was not a dictionary",
        )

    def test_rejects_malformed_invocation_status(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                    {"CommandInvocations": [{"Status": []}]},
                ],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager command command-1 returned invocation 0 without a valid status",
        )
        self.assertEqual(raised.exception.values["command_id"], "command-1")
        self.assertEqual(raised.exception.values["command_invocations"], [{"status": []}])
        self.assertEqual(raised.exception.values["status"], "Success")

    def test_rejects_empty_invocation_status(self):
        client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
        module = FakeModule(send_params(wait=True), client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods"),
            patch_time(0, 1),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[
                    {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                    {"CommandInvocations": [{"Status": ""}]},
                ],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager command command-1 returned invocation 0 without a valid status",
        )

    def test_check_mode_rejects_invalid_options(self):
        module = FakeModule(send_params(timeout_seconds=29), check_mode=True)
        module.client = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "timeout_seconds must be between 30 and 2592000",
        )
        module.client.assert_not_called()
        require.assert_not_called()
