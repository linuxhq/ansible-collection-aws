from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_serial_console_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"] == {}


def test_returns_the_serial_console_access_status():
    client = Mock()
    module = FakeModule({}, client=client)
    status = {"managed_by": "account", "serial_console_access_enabled": True}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "get_serial_console_access", return_value=status) as get_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    get_status.assert_called_once_with(client, module)
    assert raised.value.values["changed"] is False
    assert raised.value.values["serial_console_access"] == status
