from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import aws_account_info
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleExit


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("account_id", [None, "123456789012"])
def test_info(check_mode, account_id):
    client = Mock()
    client.get_account_information.return_value = {"AccountName": "Production", "ResponseMetadata": {}}
    module = FakeModule({"account_id": account_id}, check_mode=check_mode, client=client)
    with patch.object(aws_account_info, "AnsibleAWSModule", return_value=module), patch.object(
        aws_account_info, "require_client_methods"
    ), pytest.raises(ModuleExit) as result:
        aws_account_info.main()

    assert result.value.values == {"changed": False, "account": {"account_name": "Production"}}
    params = {"AccountId": account_id} if account_id is not None else {}
    client.get_account_information.assert_called_once_with(**params, aws_retry=True)
    client.put_account_name.assert_not_called()
