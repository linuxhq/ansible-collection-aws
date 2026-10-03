from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ses_sandbox_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleInitialized,
)


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"] == {}
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_returns_account_details():
    module = FakeModule({}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_account", return_value={"production_access_enabled": True}),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert not raised.value.values["changed"]
    assert raised.value.values["account"]["production_access_enabled"]
