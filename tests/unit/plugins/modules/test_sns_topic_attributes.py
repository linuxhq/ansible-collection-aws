from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import sns_topic_attributes as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    documented_returns,
)


def run(module):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods


def client_with(attributes):
    return Mock(get_topic_attributes=Mock(return_value={"Attributes": attributes}))


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["topic_arn"]["required"] is True
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_changed_attribute_is_set():
    client = client_with({"KmsMasterKeyId": "old"})
    client.get_topic_attributes.side_effect = [
        {"Attributes": {"KmsMasterKeyId": "old"}},
        {"Attributes": {"KmsMasterKeyId": "new"}},
    ]
    result, _require = run(FakeModule({"kms_master_key_id": "new", "topic_arn": "arn:topic"}, client=client))

    assert result.values["changed"]
    assert result.values["attributes"]["kms_master_key_id"] == "new"
    client.set_topic_attributes.assert_called_once_with(
        AttributeName="KmsMasterKeyId", AttributeValue="new", TopicArn="arn:topic", aws_retry=True
    )


def test_check_mode_does_not_set_changed_attribute():
    client = client_with({"KmsMasterKeyId": "old"})
    result, _require = run(
        FakeModule({"kms_master_key_id": "new", "topic_arn": "arn:topic"}, check_mode=True, client=client)
    )

    assert result.values["changed"]
    client.set_topic_attributes.assert_not_called()


@pytest.mark.parametrize(("current", "desired"), [({"KmsMasterKeyId": "alias/aws/sns"}, "alias/aws/sns"), ({}, "")])
def test_matching_attribute_is_unchanged(current, desired):
    client = client_with(current)
    result, _require = run(FakeModule({"kms_master_key_id": desired, "topic_arn": "arn:topic"}, client=client))

    assert not result.values["changed"]
    client.set_topic_attributes.assert_not_called()


def test_missing_topic_fails_in_check_mode():
    error = ClientError({"Error": {"Code": "NotFound", "Message": "missing"}}, "GetTopicAttributes")
    client = Mock(get_topic_attributes=Mock(side_effect=error))
    result, _require = run(
        FakeModule({"kms_master_key_id": "new", "topic_arn": "arn:missing"}, check_mode=True, client=client)
    )

    assert result.values["msg"] == "AWS Simple Notification Service topic arn:missing does not exist"
    client.set_topic_attributes.assert_not_called()


def test_report_only_mode_does_not_require_set_method():
    client = client_with({})
    module = FakeModule({"kms_master_key_id": None, "topic_arn": "arn:topic"}, client=client)
    result, require_client_methods = run(module)

    assert not result.values["changed"]
    require_client_methods.assert_called_once_with(module, client, "SNS", {"get_topic_attributes": ("TopicArn",)})
    client.set_topic_attributes.assert_not_called()


def test_rejects_malformed_get_response():
    client = Mock(get_topic_attributes=Mock(return_value={"Attributes": None}))
    result, _require = run(FakeModule({"kms_master_key_id": None, "topic_arn": "arn:topic"}, client=client))

    assert result.values["msg"] == "Unexpected response while getting topic attributes for arn:topic"


def test_return_documents_main_topic_attributes():
    contains = documented_returns(plugin)["attributes"]["contains"]
    expected = {
        "delivery_policy",
        "display_name",
        "effective_delivery_policy",
        "kms_master_key_id",
        "owner",
        "policy",
        "subscriptions_confirmed",
        "subscriptions_deleted",
        "subscriptions_pending",
        "topic_arn",
    }

    assert expected <= set(contains)
    assert all(field["type"] == "str" for field in contains.values())


def test_all_topic_attributes_are_returned_snake_cased():
    client = client_with({"DisplayName": "Example", "SubscriptionsConfirmed": "1", "TopicArn": "arn:topic"})
    result, _require = run(FakeModule({"kms_master_key_id": None, "topic_arn": "arn:topic"}, client=client))

    assert result.values["attributes"] == {
        "display_name": "Example",
        "subscriptions_confirmed": "1",
        "topic_arn": "arn:topic",
    }


def test_result_is_read_again_after_setting_the_attribute():
    client = Mock(
        get_topic_attributes=Mock(
            side_effect=[
                {"Attributes": {"TopicArn": "arn:topic"}},
                {"Attributes": {"KmsMasterKeyId": "arn:aws:kms:us-east-1:123456789012:alias/aws/sns"}},
            ]
        )
    )
    result, _require = run(FakeModule({"kms_master_key_id": "alias/aws/sns", "topic_arn": "arn:topic"}, client=client))

    assert result.values == {
        "attributes": {"kms_master_key_id": "arn:aws:kms:us-east-1:123456789012:alias/aws/sns"},
        "changed": True,
        "topic_arn": "arn:topic",
    }
    assert client.get_topic_attributes.call_count == 2


def test_check_mode_predicts_the_attribute_without_reading_again():
    client = client_with({"TopicArn": "arn:topic"})
    result, _require = run(
        FakeModule({"kms_master_key_id": "alias/aws/sns", "topic_arn": "arn:topic"}, check_mode=True, client=client)
    )

    assert result.values["attributes"] == {"kms_master_key_id": "alias/aws/sns", "topic_arn": "arn:topic"}
    assert client.get_topic_attributes.call_count == 1


def test_check_mode_omits_the_key_when_disabling_encryption():
    client = client_with({"KmsMasterKeyId": "alias/aws/sns", "TopicArn": "arn:topic"})
    result, _require = run(
        FakeModule({"kms_master_key_id": "", "topic_arn": "arn:topic"}, check_mode=True, client=client)
    )

    assert result.values["changed"] is True
    assert result.values["attributes"] == {"topic_arn": "arn:topic"}
    client.set_topic_attributes.assert_not_called()
    assert client.get_topic_attributes.call_count == 1


def test_read_failure_after_setting_the_attribute_reports_changed():
    error = ClientError({"Error": {"Code": "InternalError", "Message": "failed"}}, "GetTopicAttributes")
    client = Mock(get_topic_attributes=Mock(side_effect=[{"Attributes": {}}, error]))
    result, _require = run(FakeModule({"kms_master_key_id": "alias/aws/sns", "topic_arn": "arn:topic"}, client=client))

    assert isinstance(result, ModuleFail)
    assert result.values["changed"] is True
    assert result.values["msg"] == "Unable to get AWS Simple Notification Service topic attributes for arn:topic"
    client.set_topic_attributes.assert_called_once()


def test_set_failure_reports_unchanged():
    error = ClientError({"Error": {"Code": "InvalidParameter", "Message": "bad"}}, "SetTopicAttributes")
    client = client_with({})
    client.set_topic_attributes.side_effect = error
    result, _require = run(FakeModule({"kms_master_key_id": "alias/aws/sns", "topic_arn": "arn:topic"}, client=client))

    assert isinstance(result, ModuleFail)
    assert not result.values.get("changed")
    assert client.get_topic_attributes.call_count == 1
