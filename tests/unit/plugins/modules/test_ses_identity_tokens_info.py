from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ses_identity_tokens_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class SesIdentityTokensInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["identity"]["required"] is True

    def test_rejects_email_identity_before_mutating_verification_calls(self):
        module = FakeModule({"identity": "user@example.com"})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("domain name", raised.exception.values["msg"])

    def test_rejects_empty_identity(self):
        module = FakeModule({"identity": ""})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(raised.exception.values["msg"], "identity must not be empty")

    def test_check_mode_does_not_call_verification_apis(self):
        client = Mock()
        module = FakeModule({"identity": "example.com"}, check_mode=True, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        client.verify_domain_dkim.assert_not_called()
        client.verify_domain_identity.assert_not_called()
        self.assertEqual(raised.exception.values["dkim_tokens"], [])

    def test_missing_tokens_are_rejected(self):
        client = Mock()
        client.verify_domain_dkim.return_value = {"DkimTokens": []}
        client.verify_domain_identity.return_value = {}
        module = FakeModule({"identity": "example.com"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "AWS SES did not return domain tokens for example.com",
        )

    def test_fetches_tokens_without_identity_lookup(self):
        client = Mock()
        client.verify_domain_dkim.return_value = {"DkimTokens": ["dkim-token"]}
        client.verify_domain_identity.return_value = {"VerificationToken": "verification-token"}
        module = FakeModule({"identity": "new.example.com"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        client.verify_domain_dkim.assert_called_once_with(Domain="new.example.com", aws_retry=True)
        client.verify_domain_identity.assert_called_once_with(Domain="new.example.com", aws_retry=True)
        self.assertEqual(raised.exception.values["dkim_tokens"], ["dkim-token"])
        self.assertEqual(raised.exception.values["verification_token"], "verification-token")

    def test_invalid_token_response_is_rejected(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.domain_tokens_from_responses(module, [], {}, "example.com")

        self.assertIn("invalid domain token responses", raised.exception.values["msg"])

    def test_invalid_dkim_token_is_rejected(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.domain_tokens_from_responses(
                module,
                {"DkimTokens": [None]},
                {"VerificationToken": "verification-token"},
                "example.com",
            )

        self.assertIn("did not return domain tokens", raised.exception.values["msg"])
