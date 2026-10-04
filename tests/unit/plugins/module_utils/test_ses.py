# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.ses import get_account
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


def test_account_response_is_normalized_without_metadata():
    client = Mock(
        get_account=Mock(return_value={"ProductionAccessEnabled": True, "ResponseMetadata": {"RequestId": "request"}})
    )

    assert get_account(client, Mock()) == {"production_access_enabled": True}
    client.get_account.assert_called_once_with(aws_retry=True)


def test_invalid_account_response_is_rejected():
    client = Mock(get_account=Mock(return_value=[]))

    with pytest.raises(ModuleFail) as raised:
        get_account(client, FakeModule({}))

    assert raised.value.values["msg"] == "AWS Simple Email Service returned an invalid account response"
