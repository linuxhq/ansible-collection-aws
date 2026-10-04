from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import ec2_serial_console as helper
from ansible_collections.linuxhq.aws.plugins.modules import ec2_serial_console_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"] == {}


def test_response_metadata_is_removed():
    client = Mock(
        get_serial_console_access_status=Mock(
            return_value={
                "ManagedBy": "declarative-policy",
                "SerialConsoleAccessEnabled": True,
                "ResponseMetadata": {"RequestId": "request"},
            }
        )
    )
    module = FakeModule({}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(helper, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["serial_console_access"] == {
        "managed_by": "declarative-policy",
        "serial_console_access_enabled": True,
    }


def test_rejects_invalid_serial_console_status():
    client = Mock(get_serial_console_access_status=Mock(return_value={}))
    module = FakeModule({}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(helper, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "invalid serial console access status" in raised.value.values["msg"]
