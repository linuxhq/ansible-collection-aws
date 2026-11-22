from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.module_utils.common.parameters import remove_values

from ansible_collections.linuxhq.aws.plugins.module_utils import sdk, wait
from ansible_collections.linuxhq.aws.plugins.modules import ssm_send_command as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
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


@contextmanager
def patch_time(*monotonic_values):
    mocked_time = SimpleNamespace(
        monotonic=Mock(side_effect=monotonic_values),
        sleep=Mock(),
    )
    # wait_deadline reads the clock through module_utils.wait, so both share one mocked clock.
    with patch.object(plugin, "time", mocked_time), patch.object(wait, "time", mocked_time):
        yield mocked_time


def test_equivalent_targets_are_sent_once():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(
        send_params(
            instance_ids=None,
            targets=[{"key": "tag:Role", "values": ["web", "web"]}, {"key": "tag:Role", "values": ["web"]}],
        ),
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert client.send_command.call_args.kwargs["Targets"] == [{"Key": "tag:Role", "Values": ["web"]}]


def test_module_contract():
    options = assert_module_contract(plugin)
    # Modules return provider data unmodified; callers set task-level no_log for secret parameters.
    assert "no_log" not in options["argument_spec"]["parameters"]


def test_parameter_values_do_not_mask_returned_values():
    # Ansible masks every no_log value wherever it occurs in the result, including inside command_id.
    argument_spec = assert_module_contract(plugin)["argument_spec"]
    validated = ArgumentSpecValidator(argument_spec).validate(send_params(parameters={"commands": ["a60b", "1600"]}))
    result = {
        "command": {"command_id": "a60b-1600", "parameters": {"commands": ["a60b", "1600"]}},
        "command_id": "a60b-1600",
    }

    assert validated.error_messages == []
    assert remove_values(result, validated._no_log_values) == result


def test_command_normalization_preserves_compatible_request_keys():
    assert plugin.normalize_command(
        {
            "CommandId": "command-1",
            "Parameters": {"commands": ["echo test"]},
            "Status": "Success",
            "Targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
        }
    ) == {
        "command_id": "command-1",
        "parameters": {"commands": ["echo test"]},
        "status": "Success",
        "targets": [{"Key": "InstanceIds", "Values": ["i-1"]}],
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"document_name": " "},
        {"instance_ids": [" "]},
        {"instance_ids": [f"i-{index}" for index in range(51)]},
        {"instance_ids": None, "targets": [{"key": " ", "values": ["i-1"]}]},
        {"instance_ids": None, "targets": [{"key": f"tag:Role{index}", "values": ["web"]} for index in range(6)]},
        {"max_concurrency": ""},
        {"max_errors": " "},
        {"parameters": {"commands": "uptime"}},
        {"timeout_seconds": 29},
        {"instance_ids": []},
        {"instance_ids": None, "targets": []},
    ],
    ids=[
        "document-name",
        "instance-id",
        "instance-count",
        "target-key",
        "target-count",
        "concurrency",
        "errors",
        "parameters",
        "timeout",
        "empty-instance-ids",
        "empty-targets",
    ],
)
def test_check_mode_leaves_send_command_validation_to_aws(overrides):
    module = FakeModule(send_params(**overrides), check_mode=True)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"changed": True}


def test_wait_returns_terminal_command_and_invocations():
    client = Mock()
    client.send_command.return_value = {"Command": {"CommandId": "command-1", "Status": "Pending"}}
    module = FakeModule(
        send_params(instance_ids=["i-1", "i-1"], parameters={"commands": ["true"]}, wait=True), client=client
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch_time(0, 1),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                {"CommandInvocations": [{"InstanceId": "i-1", "Status": "Success"}]},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["status"] == "Success"
    assert raised.value.values["command_invocations"] == [{"instance_id": "i-1", "status": "Success"}]
    assert client.send_command.call_args.kwargs["InstanceIds"] == ["i-1"]
    assert "Targets" not in client.send_command.call_args.kwargs


def test_wait_retries_empty_invocations_when_targets_exist():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(wait=True), client=client)
    command = {"CommandId": "command-1", "Status": "Success", "TargetCount": 1}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch_time(0, 1, 2, 3),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [command]},
                {"CommandInvocations": []},
                {"Commands": [command]},
                {"CommandInvocations": [{"InstanceId": "i-1", "Status": "Success"}]},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["command_invocations"] == [{"instance_id": "i-1", "status": "Success"}]


def test_wait_retries_when_an_invocation_has_no_status():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(instance_ids=["i-1", "i-2"], wait=True), client=client)
    command = {"CommandId": "command-1", "Status": "Success", "TargetCount": 2}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch_time(0, 1, 2, 3),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [command]},
                {"CommandInvocations": [{"InstanceId": "i-1", "Status": "Success"}, {"InstanceId": "i-2"}]},
                {"Commands": [command]},
                {
                    "CommandInvocations": [
                        {"InstanceId": "i-1", "Status": "Success"},
                        {"InstanceId": "i-2", "Status": "Success"},
                    ]
                },
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert len(raised.value.values["command_invocations"]) == 2


def test_wait_retries_until_terminal_target_count_is_known():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(wait=True), client=client)
    module.warn = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch_time(0, 1, 2, 3),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                {"CommandInvocations": []},
                {"Commands": [{"CommandId": "command-1", "Status": "Success", "TargetCount": 0}]},
                {"CommandInvocations": []},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["command"]["target_count"] == 0
    module.warn.assert_called_once()


def test_failed_command_is_not_hidden_by_successful_invocations():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(wait=True), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch_time(0, 1),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [{"CommandId": "command-1", "Status": "Failed"}]},
                {"CommandInvocations": [{"Status": "Success"}]},
            ],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["status"] == "Failed"


def test_check_mode_checks_client_capabilities_without_sending():
    client = Mock()
    module = FakeModule(send_params(), check_mode=True, client=client)
    module.client = Mock(return_value=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"]
    module.client.assert_called_once()
    require.assert_called_once()
    client.send_command.assert_not_called()


def test_client_methods_are_checked_before_sending():
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
            plugin, "require_client_methods", side_effect=lambda *args, **kwargs: calls.append("require_client_methods")
        ),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert calls == ["require_client_methods", "send_command"]


def test_timeout_before_first_poll_returns_empty_invocations():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(wait=True), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods"),
        patch_time(0, 11),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["command_invocations"] == []
    assert raised.value.values["status"] is None
    assert raised.value.values["msg"] == "Timed out waiting for AWS Systems Manager command command-1"


def test_wait_sleep_is_bounded_by_remaining_timeout():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(wait=True, wait_delay=5, wait_timeout=10), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods"),
        patch_time(0, 9, 9.75, 10) as mocked_time,
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[{"Commands": [{"CommandId": "command-1", "Status": "Pending"}]}, {"CommandInvocations": []}],
        ),
        pytest.raises(ModuleFail),
    ):
        plugin.main()

    mocked_time.sleep.assert_called_once_with(0.25)


def test_wait_retries_when_command_has_no_status():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1"}}))
    module = FakeModule(send_params(wait=True), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods"),
        patch_time(0, 1, 2, 3),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [{"CommandId": "command-1"}]},
                {"CommandInvocations": []},
                {"Commands": [{"CommandId": "command-1", "Status": "Success"}]},
                {"CommandInvocations": [{"Status": "Success"}]},
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["status"] == "Success"


def test_rate_controls_and_empty_parameter_lists_are_sent_unchanged():
    client = Mock(send_command=Mock(return_value={"Command": {"CommandId": "command-1", "Status": "Pending"}}))
    module = FakeModule(
        send_params(max_concurrency="10%", max_errors="0", parameters={"commands": [], "workingDirectory": [""]}),
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"]
    client.send_command.assert_called_once_with(
        DocumentName="AWS-RunShellScript",
        InstanceIds=["i-1"],
        MaxConcurrency="10%",
        MaxErrors="0",
        Parameters={"commands": [], "workingDirectory": [""]},
        aws_retry=True,
    )


def test_ssm_wait_tolerates_initially_invisible_command():
    client = Mock()
    client.send_command.return_value = {"Command": {"CommandId": "command-1", "Status": "Pending"}}
    module = FakeModule(send_params(wait=True), client=client)
    responses = [
        {"Commands": []},
        {"CommandInvocations": []},
        {"Commands": [{"CommandId": "command-1", "Status": "Success", "TargetCount": 1}]},
        {"CommandInvocations": [{"InstanceId": "i-1", "Status": "Success"}]},
    ]
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(sdk, "paginated_query_with_retries", side_effect=responses),
        patch.object(plugin.time, "sleep"),
        pytest.raises(ModuleExit),
    ):
        plugin.main()


def test_ssm_invisible_command_still_times_out():
    client = Mock()
    client.send_command.return_value = {"Command": {"CommandId": "command-1", "Status": "Pending"}}
    module = FakeModule(send_params(wait=True), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": []},
                {"CommandInvocations": []},
            ],
        ),
        patch_time(0, 1, 2, 11),
        pytest.raises(ModuleFail) as result,
    ):
        plugin.main()

    assert result.value.values["msg"] == "Timed out waiting for AWS Systems Manager command command-1"
    assert result.value.values["changed"] is True
    client.send_command.assert_called_once()


@pytest.mark.parametrize("partial_copies", [1, 2])
def test_ssm_waits_for_all_target_invocations(partial_copies):
    command = {
        "CommandId": "review-command",
        "Status": "Success",
        "TargetCount": 2,
        "CompletedCount": 2,
        "ErrorCount": 1,
    }
    success = {"CommandId": "review-command", "InstanceId": "i-1", "Status": "Success"}
    failed = {"CommandId": "review-command", "InstanceId": "i-2", "Status": "Failed"}
    client = Mock(send_command=Mock(return_value={"Command": command}))
    module = FakeModule(send_params(wait=True, instance_ids=["i-1", "i-2"], max_errors="2"), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin.time, "sleep"),
        patch.object(
            sdk,
            "paginated_query_with_retries",
            side_effect=[
                {"Commands": [command]},
                {"CommandInvocations": [success] * partial_copies},
                {"Commands": [command]},
                {"CommandInvocations": [success, failed]},
            ],
        ) as query,
        pytest.raises(ModuleFail) as result,
    ):
        plugin.main()

    assert query.call_count == 4
    assert "did not complete successfully" in result.value.values["msg"]
    assert len(result.value.values["command_invocations"]) == 2
