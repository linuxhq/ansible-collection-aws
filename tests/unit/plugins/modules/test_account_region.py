from unittest.mock import Mock, call, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import account_region as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_sdk_validation_requires_region_name():
    for state in ("present", "absent"):
        module = Mock(
            params={
                "name": "af-south-1",
                "state": state,
                "wait": False,
                "wait_delay": 30,
                "wait_timeout": 1800,
            },
            client=Mock(return_value=Mock()),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, f"ensure_{state}"),
        ):
            plugin.main()

        methods = require.call_args.args[3]
        assert methods == {"get_region_opt_status": ("RegionName",)}


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["wait_timeout"]["default"] == 1800


def test_get_region_opt_status_rejects_missing_status():
    module = FakeModule({"name": "af-south-1"})
    client = Mock()
    client.get_region_opt_status.return_value = {}

    with pytest.raises(ModuleFail) as raised:
        plugin.get_region_opt_status(client, module)

    client.get_region_opt_status.assert_called_once_with(
        RegionName="af-south-1",
        aws_retry=True,
    )
    assert "af-south-1" in raised.value.values["msg"]
    assert "unexpected status None" in raised.value.values["msg"]


def test_check_mode_predicts_region_enablement():
    module = FakeModule({"name": "af-south-1", "wait": True}, check_mode=True)
    client = Mock()
    with (
        patch.object(plugin, "get_region_opt_status", return_value="DISABLED"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    client.enable_region.assert_not_called()
    assert raised.value.values["region_opt_status"] == "ENABLED"
    assert raised.value.values["changed"]


def test_default_region_cannot_be_disabled():
    module = FakeModule({"name": "us-east-1", "wait": True})
    with (
        patch.object(
            plugin,
            "get_region_opt_status",
            return_value="ENABLED_BY_DEFAULT",
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(Mock(), module)

    assert "default Regions cannot be disabled" in raised.value.values["msg"]


def test_enable_waits_for_disabling_region_even_without_final_wait():
    module = FakeModule({"name": "af-south-1", "wait": False})
    client = Mock()
    with (
        patch.object(
            plugin,
            "get_region_opt_status",
            side_effect=["DISABLING", "ENABLING"],
        ),
        patch.object(plugin, "wait_for_status") as wait_for_status,
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait_for_status.assert_called_once_with(client, module, "region_disabled", plugin.ABSENT_STEADY_STATUSES)
    client.enable_region.assert_called_once_with(RegionName="af-south-1", aws_retry=True)
    assert require.call_args.args[3] == {"enable_region": ("RegionName",)}


def test_disable_waits_for_enabling_region_even_without_final_wait():
    module = FakeModule({"name": "af-south-1", "wait": False})
    client = Mock()
    with (
        patch.object(
            plugin,
            "get_region_opt_status",
            side_effect=["ENABLING", "DISABLING"],
        ),
        patch.object(plugin, "wait_for_status") as wait_for_status,
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_absent(client, module)

    wait_for_status.assert_called_once_with(client, module, "region_enabled", plugin.PRESENT_STEADY_STATUSES)
    client.disable_region.assert_called_once_with(RegionName="af-south-1", aws_retry=True)
    assert require.call_args.args[3] == {"disable_region": ("RegionName",)}


def test_account_id_is_sent_with_every_region_call():
    module = FakeModule({"account_id": "123456789012", "name": "af-south-1", "wait": False})
    client = Mock()
    client.get_region_opt_status.side_effect = [
        {"RegionOptStatus": "DISABLED"},
        {"RegionOptStatus": "ENABLING"},
    ]
    with (
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    request = {"AccountId": "123456789012", "RegionName": "af-south-1"}
    assert client.get_region_opt_status.call_args_list == [call(**request, aws_retry=True)] * 2
    client.enable_region.assert_called_once_with(**request, aws_retry=True)
    assert require.call_args.args[3] == {"enable_region": ("AccountId", "RegionName")}
    assert result.value.values["region_opt_status"] == "ENABLING"


def test_account_id_is_sent_to_the_waiter():
    module = FakeModule({"account_id": "123456789012", "name": "af-south-1"})
    client = Mock()
    client.get_region_opt_status.return_value = {"RegionOptStatus": "ENABLED"}
    with patch.object(plugin, "run_waiter") as run_waiter:
        plugin.wait_for_status(client, module, "region_enabled", plugin.PRESENT_STEADY_STATUSES)

    assert run_waiter.call_args.kwargs == {"AccountId": "123456789012", "RegionName": "af-south-1", "changed": False}
    assert "af-south-1 in account 123456789012" in run_waiter.call_args.args[4]


@pytest.mark.parametrize("account_id", ["", "123", "a" * 12])
def test_invalid_account_id_is_rejected_before_api_calls(account_id):
    module = FakeModule(
        {
            "account_id": account_id,
            "name": "af-south-1",
            "state": "present",
            "wait": True,
            "wait_delay": 30,
            "wait_timeout": 1800,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail, match="12 digits"),
    ):
        plugin.main()

    module._client.get_region_opt_status.assert_not_called()


@pytest.mark.parametrize(
    ("state", "previous", "mutation"),
    [("present", "DISABLED", "enable_region"), ("absent", "ENABLED", "disable_region")],
)
def test_waiter_failure_after_mutation_reports_changed(state, previous, mutation):
    module = FakeModule({"name": "af-south-1", "state": state, "wait": True, "wait_delay": 1, "wait_timeout": 1})
    client = Mock()
    with (
        patch.object(plugin, "get_region_opt_status", return_value=previous),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "run_waiter", side_effect=ModuleFail({"msg": "timed out"})) as run_waiter,
        pytest.raises(ModuleFail),
    ):
        getattr(plugin, f"ensure_{state}")(client, module)

    getattr(client, mutation).assert_called_once_with(RegionName="af-south-1", aws_retry=True)
    assert run_waiter.call_args.kwargs["changed"] is True


@pytest.mark.parametrize(
    ("state", "previous", "mutation"),
    [("present", "DISABLED", "enable_region"), ("absent", "ENABLED", "disable_region")],
)
def test_status_failure_after_mutation_reports_changed(state, previous, mutation):
    module = FakeModule({"name": "af-south-1", "state": state, "wait": False})
    client = Mock()
    client.get_region_opt_status.side_effect = [
        {"RegionOptStatus": previous},
        plugin.ClientError({"Error": {"Code": "InternalServerException", "Message": "boom"}}, "GetRegionOptStatus"),
    ]
    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        getattr(plugin, f"ensure_{state}")(client, module)

    getattr(client, mutation).assert_called_once_with(RegionName="af-south-1", aws_retry=True)
    assert raised.value.values["changed"] is True


def test_status_failure_before_mutation_reports_unchanged():
    module = FakeModule({"name": "af-south-1"})
    client = Mock()
    client.get_region_opt_status.return_value = {"RegionOptStatus": "UNKNOWN"}

    with pytest.raises(ModuleFail) as raised:
        plugin.get_region_opt_status(client, module)

    assert raised.value.values["changed"] is False
