from unittest.mock import Mock

from ansible_collections.linuxhq.aws.plugins.module_utils.sns import get_sms_attributes
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule


def test_get_sms_attributes_passes_the_request():
    client = Mock(get_sms_attributes=Mock(return_value={"attributes": {"DefaultSMSType": "Transactional"}}))

    assert get_sms_attributes(client, FakeModule({}), attributes=["DefaultSMSType"]) == {
        "DefaultSMSType": "Transactional"
    }
    client.get_sms_attributes.assert_called_once_with(attributes=["DefaultSMSType"], aws_retry=True)


def test_get_sms_attributes_defaults_missing_attributes_to_empty():
    client = Mock(get_sms_attributes=Mock(return_value={}))

    assert get_sms_attributes(client, FakeModule({})) == {}
