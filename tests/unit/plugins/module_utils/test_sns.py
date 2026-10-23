from unittest.mock import Mock

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.sns import get_sms_attributes
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


def test_get_sms_attributes_passes_the_request():
    client = Mock(get_sms_attributes=Mock(return_value={"attributes": {"DefaultSMSType": "Transactional"}}))

    assert get_sms_attributes(client, FakeModule({}), attributes=["DefaultSMSType"]) == {
        "DefaultSMSType": "Transactional"
    }
    client.get_sms_attributes.assert_called_once_with(attributes=["DefaultSMSType"], aws_retry=True)


def test_get_sms_attributes_defaults_missing_attributes_to_empty():
    client = Mock(get_sms_attributes=Mock(return_value={}))

    assert get_sms_attributes(client, FakeModule({})) == {}


@pytest.mark.parametrize("response", [None, {"attributes": []}])
@pytest.mark.parametrize("changed", [False, True])
def test_get_sms_attributes_rejects_malformed_responses(response, changed):
    client = Mock(get_sms_attributes=Mock(return_value=response))

    with pytest.raises(ModuleFail) as raised:
        get_sms_attributes(client, FakeModule({}), changed=changed)

    assert raised.value.values == {
        "changed": changed,
        "msg": "Unexpected response while getting AWS Simple Notification Service SMS attributes",
    }
