from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import iam_account_alias as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_list_account_aliases_uses_the_shared_paginated_query():
    client = Mock()
    module = FakeModule({})
    with patch.object(plugin, "query_list", return_value=["b-alias", "a-alias"]) as query:
        assert plugin.list_account_aliases(client, module) == ["a-alias", "b-alias"]

    query.assert_called_once_with(
        module, client, "list_account_aliases", "AccountAliases", "Unable to list AWS IAM account aliases"
    )


def test_delete_tolerates_alias_disappearing():
    client = Mock()
    client.delete_account_alias.side_effect = plugin.ClientError(
        {"Error": {"Code": "NoSuchEntity", "Message": "gone"}},
        "DeleteAccountAlias",
    )
    with patch.object(plugin, "require_client_methods"):
        assert plugin.delete_account_alias(client, FakeModule({}), "alias") is False


def test_absent_reports_unchanged_when_alias_disappears_during_delete():
    client = Mock()
    client.delete_account_alias.side_effect = plugin.ClientError(
        {"Error": {"Code": "NoSuchEntity", "Message": "gone"}},
        "DeleteAccountAlias",
    )
    with (
        patch.object(plugin, "list_account_aliases", return_value=["alias"]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, FakeModule({"name": "alias"}))

    assert raised.value.values["changed"] is False
    assert raised.value.values["account_aliases"] == []


def test_module_contract():
    assert_module_contract(plugin)


def test_existing_alias_is_replaced():
    client = Mock()
    module = FakeModule({"name": "new-alias"})
    with (
        patch.object(plugin, "list_account_aliases", return_value=["old-alias"]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    client.delete_account_alias.assert_not_called()
    client.create_account_alias.assert_called_once_with(AccountAlias="new-alias", aws_retry=True)


def test_failed_replacement_preserves_existing_alias():
    client = Mock()
    client.create_account_alias.side_effect = plugin.ClientError(
        {"Error": {"Code": "EntityAlreadyExists", "Message": "Alias already taken"}},
        "CreateAccountAlias",
    )
    with (
        patch.object(plugin, "list_account_aliases", return_value=["old-alias"]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_present(client, FakeModule({"name": "taken-alias"}))

    client.delete_account_alias.assert_not_called()


def test_present_state_only_requires_list_before_reconciliation():
    module = Mock(
        check_mode=True,
        params={"name": "new-alias", "state": "present"},
        client=Mock(return_value=Mock()),
    )
    require_client_methods = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "ensure_present"),
        patch.object(plugin, "require_client_methods", require_client_methods),
    ):
        plugin.main()

    require_client_methods.assert_called_once_with(
        module,
        module.client.return_value,
        "IAM",
        {"list_account_aliases": ("Marker", "MaxItems")},
    )


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("name", "state"),
    [
        ("12345678901", "present"),
        ("1234567890134", "present"),
        ("12345678901a", "present"),
        ("1234-5678901", "present"),
        ("123456789013", "present"),
        ("Invalid--Alias", "present"),
        ("123456789013", "absent"),
    ],
)
def test_alias_names_aws_accepts_reach_reconciliation(check_mode, name, state):
    module = FakeModule({"name": name, "state": state}, check_mode=check_mode, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_present") as ensure_present,
        patch.object(plugin, "ensure_absent") as ensure_absent,
    ):
        plugin.main()

    assert (ensure_present if state == "present" else ensure_absent).call_count == 1


def test_account_alias_retries_concurrent_modification():
    module = FakeModule({"state": "absent", "name": "example"}, client=Mock())
    original = plugin.AWSRetry.jittered_backoff
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_absent"),
        patch.object(plugin.AWSRetry, "jittered_backoff", wraps=original) as configured,
    ):
        plugin.main()

    decorator = original(retries=2, delay=0, **configured.call_args.kwargs)
    operation = Mock(
        side_effect=[
            plugin.ClientError({"Error": {"Code": "ConcurrentModification", "Message": "retry"}}, "CreateAccountAlias"),
            {},
        ]
    )
    assert decorator(operation)() == {}
    assert operation.call_count == 2
