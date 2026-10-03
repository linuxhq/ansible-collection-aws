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

    assert result.values["msg"] == "AWS Simple Notification Service topic does not exist arn:missing"
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
