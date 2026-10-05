from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import ec2_serial_console as helper
from ansible_collections.linuxhq.aws.plugins.modules import ec2_serial_console as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["state"]["choices"] == ["absent", "present"]


def test_response_metadata_is_not_returned():
    response = {"SerialConsoleAccessEnabled": True, "ResponseMetadata": {"x": 1}}
    assert plugin.normalized_serial_console_access(FakeModule({}), response) == {"serial_console_access_enabled": True}
    assert response == {"SerialConsoleAccessEnabled": True, "ResponseMetadata": {"x": 1}}


def test_rejects_invalid_serial_console_status():
    for response in ({}, {"SerialConsoleAccessEnabled": None}, None):
        with pytest.raises(ModuleFail) as raised:
            plugin.normalized_serial_console_access(FakeModule({}), response)

        assert "invalid serial console access status" in raised.value.values["msg"]


def test_check_mode_projects_enabled_state_without_mutation():
    client = Mock()
    client.get_serial_console_access_status.return_value = {"SerialConsoleAccessEnabled": False}
    module = FakeModule({"state": "present"}, check_mode=True, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(helper, "require_client_methods") as require_status,
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"]
    assert raised.value.values["serial_console_access"]["serial_console_access_enabled"]
    client.enable_serial_console_access.assert_not_called()
    require.assert_not_called()
    assert require_status.call_args.args[3] == {"get_serial_console_access_status": ()}


def test_change_keeps_status_fields_missing_from_mutation_response():
    for state, current, method in (
        ("present", False, "enable_serial_console_access"),
        ("absent", True, "disable_serial_console_access"),
    ):
        client = Mock()
        client.get_serial_console_access_status.return_value = {
            "ManagedBy": "account",
            "SerialConsoleAccessEnabled": current,
        }
        getattr(client, method).return_value = {
            "SerialConsoleAccessEnabled": not current,
            "ResponseMetadata": {"RequestId": "request"},
        }
        module = FakeModule({"state": state}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(helper, "require_client_methods"),
            patch.object(plugin, "require_client_methods"),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.main()

        assert raised.value.values["changed"]
        assert raised.value.values["serial_console_access"] == {
            "managed_by": "account",
            "serial_console_access_enabled": not current,
        }
        getattr(client, method).assert_called_once_with(aws_retry=True)


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("state", "current", "method"),
    [
        ("present", False, "enable_serial_console_access"),
        ("absent", True, "disable_serial_console_access"),
    ],
)
def test_declarative_policy_fails_before_change(check_mode, state, current, method):
    client = Mock()
    client.get_serial_console_access_status.return_value = {
        "ManagedBy": "declarative-policy",
        "SerialConsoleAccessEnabled": current,
    }
    module = FakeModule({"state": state}, check_mode=check_mode, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(helper, "require_client_methods"),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == (
        "EC2 serial console access in region us-east-1 is managed by a declarative policy and cannot be changed"
    )
    require.assert_not_called()
    getattr(client, method).assert_not_called()


def test_declarative_policy_without_change_reports_current_state():
    client = Mock()
    client.get_serial_console_access_status.return_value = {
        "ManagedBy": "declarative-policy",
        "SerialConsoleAccessEnabled": True,
    }
    module = FakeModule({"state": "present"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(helper, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert not raised.value.values["changed"]
    assert raised.value.values["serial_console_access"] == {
        "managed_by": "declarative-policy",
        "serial_console_access_enabled": True,
    }
    client.enable_serial_console_access.assert_not_called()
