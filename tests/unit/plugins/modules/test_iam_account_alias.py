from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import iam_account_alias as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class IamAccountAliasTests(TestCase):
    def test_list_account_aliases_rejects_invalid_response(self):
        module = FakeModule({})
        with (
            patch.object(plugin, "paginated_query_with_retries", return_value={}),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.list_account_aliases(Mock(), module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list AWS IAM account aliases: AWS returned an invalid response",
        )

    def test_delete_tolerates_alias_disappearing(self):
        client = Mock()
        client.delete_account_alias.side_effect = plugin.ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "gone"}},
            "DeleteAccountAlias",
        )
        with patch.object(plugin, "require_client_methods"):
            plugin.delete_account_alias(client, FakeModule({}), "alias")

    def test_module_contract(self):
        assert_module_contract(self, plugin)

    def test_existing_alias_is_replaced(self):
        client = Mock()
        module = FakeModule({"name": "new-alias"})
        with (
            patch.object(plugin, "list_account_aliases", return_value=["old-alias"]),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        client.delete_account_alias.assert_not_called()
        client.create_account_alias.assert_called_once_with(AccountAlias="new-alias", aws_retry=True)

    def test_failed_replacement_preserves_existing_alias(self):
        client = Mock()
        client.create_account_alias.side_effect = plugin.ClientError(
            {"Error": {"Code": "EntityAlreadyExists", "Message": "Alias already taken"}},
            "CreateAccountAlias",
        )
        with (
            patch.object(plugin, "list_account_aliases", return_value=["old-alias"]),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail),
        ):
            plugin.ensure_present(client, FakeModule({"name": "taken-alias"}))

        client.delete_account_alias.assert_not_called()

    def test_present_state_only_requires_list_before_reconciliation(self):
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

    def test_invalid_alias_is_rejected_before_api_calls(self):
        module = FakeModule({"name": "Invalid--Alias", "state": "present"})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("lowercase letters", raised.exception.values["msg"])


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
