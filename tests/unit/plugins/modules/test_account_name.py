from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from ansible_collections.linuxhq.aws.plugins.modules import account_name, aws_account_info
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleExit, ModuleFail


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("account_id", [None, "123456789012"])
@pytest.mark.parametrize("current", ["Production", "Previous"])
def test_manager(check_mode, account_id, current):
    client = Mock()
    client.get_account_information.side_effect = [{"AccountName": current}, {"AccountName": "Production"}]
    module = FakeModule({"name": "Production", "account_id": account_id}, check_mode=check_mode, client=client)
    with patch.object(account_name, "AnsibleAWSModule", return_value=module), patch.object(
        account_name, "require_client_methods"
    ) as gate, pytest.raises(ModuleExit) as result:
        account_name.main()

    assert result.value.values == {"changed": current != "Production", "account": {"account_name": "Production"}}
    params = {"AccountId": account_id} if account_id is not None else {}
    client.get_account_information.assert_any_call(**params, aws_retry=True)
    if current != "Production" and not check_mode:
        client.put_account_name.assert_called_once_with(AccountName="Production", **params, aws_retry=True)
        assert client.get_account_information.call_count == 2
        assert gate.call_count == 2
    else:
        client.put_account_name.assert_not_called()
        assert gate.call_count == 1


@pytest.mark.parametrize("name", ["", "x" * 51, "<name>", "café", "line\n", "tab\t"])
def test_invalid_name(name):
    module = FakeModule({"name": name, "account_id": None}, client=Mock())
    with patch.object(account_name, "AnsibleAWSModule", return_value=module), pytest.raises(ModuleFail):
        account_name.main()

    module._client.get_account_information.assert_not_called()


@pytest.mark.parametrize("plugin", [account_name, aws_account_info])
@pytest.mark.parametrize("account_id", ["", "123", "a" * 12, "１２３４５６７８９０１２"])
def test_invalid_account_id(plugin, account_id):
    module = FakeModule({"name": "Production", "account_id": account_id}, client=Mock())
    with patch.object(plugin, "AnsibleAWSModule", return_value=module), pytest.raises(ModuleFail):
        plugin.main()

    module._client.get_account_information.assert_not_called()


@pytest.mark.parametrize("operation", ["read", "write", "reread"])
@pytest.mark.parametrize(
    "error",
    [
        ClientError({"Error": {"Code": "AccessDeniedException", "Message": "Denied"}}, "AccountOperation"),
        EndpointConnectionError(endpoint_url="https://account.amazonaws.com"),
    ],
)
def test_sdk_errors(operation, error):
    client = Mock()
    client.get_account_information.side_effect = (
        [error]
        if operation == "read"
        else [{"AccountName": "Previous"}, error] if operation == "reread" else [{"AccountName": "Previous"}]
    )
    if operation == "write":
        client.put_account_name.side_effect = error

    module = FakeModule({"name": "Production", "account_id": "123456789012"}, client=client)
    with patch.object(account_name, "require_client_methods"), pytest.raises(ModuleFail, match="123456789012"):
        account_name.ensure_present(module, client, {"AccountId": "123456789012"})
