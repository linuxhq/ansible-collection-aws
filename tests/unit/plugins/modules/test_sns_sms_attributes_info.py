from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import sns_sms_attributes_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
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
    assert captured["argument_spec"]["attributes"]["elements"] == "str"
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_client_retries_throttled():
    module = FakeModule({"attributes": None})
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin.AWSRetry, "jittered_backoff") as jittered_backoff,
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    jittered_backoff.assert_called_once_with(catch_extra_error_codes=["Throttled"])


def test_requested_attributes_are_forwarded():
    client = Mock(get_sms_attributes=Mock(return_value={"attributes": {"DefaultSMSType": "Transactional"}}))
    module = FakeModule({"attributes": ["DefaultSMSType", "DefaultSMSType"]}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert require.call_args.args[3] == {"get_sms_attributes": ("attributes",)}
    client.get_sms_attributes.assert_called_once_with(attributes=["DefaultSMSType"], aws_retry=True)
    assert raised.value.values["attributes"] == {"default_sms_type": "Transactional"}
    assert not raised.value.values["changed"]


def test_rejects_malformed_get_response():
    client = Mock(get_sms_attributes=Mock(return_value={"attributes": None}))
    module = FakeModule({"attributes": None}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert (
        raised.value.values["msg"] == "Unexpected response while getting AWS Simple Notification Service SMS attributes"
    )
