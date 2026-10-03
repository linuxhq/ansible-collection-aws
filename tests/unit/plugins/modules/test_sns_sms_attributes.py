from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import sns_sms_attributes as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)


def params(**overrides):
    values = dict.fromkeys(plugin.MANAGED_ATTRIBUTES)
    values.update(overrides)
    return values


def run(module):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["default_sms_type"]["choices"] == ["Promotional", "Transactional"]
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_client_retries_throttled():
    module = FakeModule(params())
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin.AWSRetry, "jittered_backoff") as jittered_backoff,
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    jittered_backoff.assert_called_once_with(catch_extra_error_codes=["Throttled"])


@pytest.mark.parametrize("rate", [-1, 101])
def test_rejects_sampling_rate_outside_percent(rate):
    result, _require = run(FakeModule(params(delivery_status_success_sampling_rate=rate)))

    assert "between 0 and 100" in result.values["msg"]


def test_zero_sampling_rate_is_sent():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {}}
    result, _require = run(FakeModule(params(delivery_status_success_sampling_rate=0), client=client))

    assert result.values["changed"]
    client.set_sms_attributes.assert_called_once_with(
        attributes={"DeliveryStatusSuccessSamplingRate": "0"}, aws_retry=True
    )


def test_partial_update_preserves_unmanaged_attributes():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {"DefaultSenderID": "old", "MonthlySpendLimit": "100"}}
    result, _require = run(FakeModule(params(default_sender_id="new"), client=client))

    client.set_sms_attributes.assert_called_once_with(attributes={"DefaultSenderID": "new"}, aws_retry=True)
    assert result.values["attributes"]["monthly_spend_limit"] == "100"


def test_matching_attributes_are_unchanged():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {"DeliveryStatusSuccessSamplingRate": "10"}}
    result, _require = run(FakeModule(params(delivery_status_success_sampling_rate=10), client=client))

    assert not result.values["changed"]
    client.set_sms_attributes.assert_not_called()


def test_check_mode_predicts_without_setting():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {}}
    result, _require = run(FakeModule(params(default_sms_type="Transactional"), client=client, check_mode=True))

    assert result.values["changed"]
    assert result.values["attributes"]["default_sms_type"] == "Transactional"
    client.set_sms_attributes.assert_not_called()


def test_report_only_mode_does_not_require_set_method():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {}}
    module = FakeModule(params(), client=client)
    result, require_client_methods = run(module)

    assert not result.values["changed"]
    require_client_methods.assert_called_once_with(module, client, "SNS", {"get_sms_attributes": ()})
    client.set_sms_attributes.assert_not_called()


def test_rejects_malformed_get_response():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": []}
    result, _require = run(FakeModule(params(), client=client))

    assert "Unexpected response" in result.values["msg"]
