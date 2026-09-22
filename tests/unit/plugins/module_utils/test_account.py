from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import account
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


@pytest.mark.parametrize("response", [None, [], {}, {"AccountName": None}, {"AccountName": ""}, {"AccountName": 123}])
def test_invalid_response(response):
    client = Mock()
    client.get_account_information.return_value = response
    with pytest.raises(ModuleFail, match="invalid response"):
        account.get_account(FakeModule({}), client, {})


def test_complete_account_information():
    client = Mock()
    created = datetime(2020, 1, 2, tzinfo=timezone.utc)
    client.get_account_information.return_value = {
        "AccountName": "Production",
        "AccountId": "123456789012",
        "AccountCreatedDate": created,
        "AccountState": "ACTIVE",
        "ResponseMetadata": {"RequestId": "ignored"},
    }
    assert account.get_account(FakeModule({}), client, {}) == {
        "account_name": "Production",
        "account_id": "123456789012",
        "account_created_date": "2020-01-02T00:00:00+00:00",
        "account_state": "ACTIVE",
    }


@pytest.mark.parametrize("field", ["AccountId", "AccountCreatedDate", "AccountState"])
def test_invalid_optional_response_fields(field):
    client = Mock()
    client.get_account_information.return_value = {"AccountName": "Production", field: 123}
    with pytest.raises(ModuleFail, match=f"invalid {field}"):
        account.get_account(FakeModule({}), client, {})
