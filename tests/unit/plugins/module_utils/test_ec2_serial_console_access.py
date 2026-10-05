from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import ec2_serial_console as helper
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


def test_gets_and_normalizes_serial_console_access():
    client = Mock(
        get_serial_console_access_status=Mock(
            return_value={
                "ManagedBy": "account",
                "SerialConsoleAccessEnabled": True,
                "ResponseMetadata": {"RequestId": "request"},
            }
        )
    )
    module = FakeModule({})
    with patch.object(helper, "require_client_methods") as require:
        assert helper.get_serial_console_access(client, module) == {
            "managed_by": "account",
            "serial_console_access_enabled": True,
        }

    require.assert_called_once_with(module, client, "EC2", {"get_serial_console_access_status": ()})
    client.get_serial_console_access_status.assert_called_once_with(aws_retry=True)


def test_reports_status_errors_with_region():
    client = Mock()
    client.get_serial_console_access_status.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}},
        "GetSerialConsoleAccessStatus",
    )
    with patch.object(helper, "require_client_methods"), pytest.raises(ModuleFail) as raised:
        helper.get_serial_console_access(client, FakeModule({}, region="eu-west-1"))

    assert raised.value.values["msg"] == "Unable to get EC2 serial console access in region eu-west-1"


def test_rejects_invalid_status():
    client = Mock(get_serial_console_access_status=Mock(return_value={"ManagedBy": "account"}))
    with patch.object(helper, "require_client_methods"), pytest.raises(ModuleFail) as raised:
        helper.get_serial_console_access(client, FakeModule({}))

    assert raised.value.values["msg"] == "EC2 returned an invalid serial console access status"
