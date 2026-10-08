from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

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


def test_empty_string_matches_omitted_attribute():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {"MonthlySpendLimit": "1"}}
    result, _require = run(FakeModule(params(default_sender_id="", usage_report_s3_bucket=""), client=client))

    assert result.values["changed"] is False
    client.set_sms_attributes.assert_not_called()


def test_empty_string_clears_configured_attribute():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {"DefaultSenderID": "old"}}
    result, _require = run(FakeModule(params(default_sender_id=""), client=client))

    assert result.values["changed"] is True
    client.set_sms_attributes.assert_called_once_with(attributes={"DefaultSenderID": ""}, aws_retry=True)


def test_result_is_read_again_after_setting_attributes():
    client = Mock(
        get_sms_attributes=Mock(
            side_effect=[
                {"attributes": {"MonthlySpendLimit": "1"}},
                {"attributes": {"MonthlySpendLimit": "25.00"}},
            ]
        )
    )
    result, _require = run(FakeModule(params(monthly_spend_limit="25"), client=client))

    assert result.values == {"attributes": {"monthly_spend_limit": "25.00"}, "changed": True}
    client.set_sms_attributes.assert_called_once_with(attributes={"MonthlySpendLimit": "25"}, aws_retry=True)
    assert client.get_sms_attributes.call_count == 2


def test_check_mode_predicts_attributes_without_reading_again():
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {"MonthlySpendLimit": "1"}}
    result, _require = run(FakeModule(params(default_sms_type="Transactional"), client=client, check_mode=True))

    assert result.values["attributes"] == {"default_sms_type": "Transactional", "monthly_spend_limit": "1"}
    assert client.get_sms_attributes.call_count == 1


def test_read_failure_after_setting_attributes_reports_changed():
    error = ClientError({"Error": {"Code": "InternalError", "Message": "failed"}}, "GetSMSAttributes")
    client = Mock(get_sms_attributes=Mock(side_effect=[{"attributes": {}}, error]))
    result, _require = run(FakeModule(params(default_sms_type="Transactional"), client=client))

    assert isinstance(result, ModuleFail)
    assert result.values["changed"] is True
    assert result.values["msg"] == "Unable to get AWS Simple Notification Service SMS attributes"
    client.set_sms_attributes.assert_called_once()


def test_malformed_read_after_setting_attributes_reports_changed():
    client = Mock(get_sms_attributes=Mock(side_effect=[{"attributes": {}}, {"attributes": []}]))
    result, _require = run(FakeModule(params(default_sms_type="Transactional"), client=client))

    assert isinstance(result, ModuleFail)
    assert result.values["changed"] is True
    assert "Unexpected response" in result.values["msg"]


def test_set_failure_reports_unchanged():
    error = ClientError({"Error": {"Code": "InvalidParameter", "Message": "bad"}}, "SetSMSAttributes")
    client = Mock()
    client.get_sms_attributes.return_value = {"attributes": {}}
    client.set_sms_attributes.side_effect = error
    result, _require = run(FakeModule(params(default_sms_type="Transactional"), client=client))

    assert isinstance(result, ModuleFail)
    assert not result.values.get("changed")
    assert client.get_sms_attributes.call_count == 1
