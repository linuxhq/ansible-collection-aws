from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import sns_sms_attributes_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleInitialized,
    assert_module_contract,
)


def test_module_contract():
    captured = assert_module_contract(plugin)

    assert captured["argument_spec"]["attributes"]["elements"] == "str"


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
