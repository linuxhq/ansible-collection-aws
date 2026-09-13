from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ses_sandbox as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


@pytest.mark.parametrize("check_mode", [False, True])
def test_omitted_contacts_preserve_existing_addresses_without_update(check_mode):
    client = Mock()
    module = FakeModule(
        {
            "additional_contact_email_addresses": [],
            "contact_language": "en",
            "mail_type": "transactional",
            "use_case_description": "Production email",
            "website_url": "https://example.com",
        },
        client=client,
        check_mode=check_mode,
    )
    account = {
        "details": {
            "additional_contact_email_addresses": ["existing@example.com"],
            "contact_language": "EN",
            "mail_type": "TRANSACTIONAL",
            "use_case_description": "Production email",
            "website_url": "https://example.com",
        },
        "production_access_enabled": True,
    }
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_account", return_value=account),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert not raised.value.values["changed"]
    assert raised.value.values["account"] == account
    client.put_account_details.assert_not_called()


class SesSandboxTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_together"] == [["use_case_description", "website_url"]]

    def test_account_details_are_deduplicated_and_sorted(self):
        assert plugin.comparable_details(
            {
                "additional_contact_email_addresses": [
                    "b@example.com",
                    "a@example.com",
                    "b@example.com",
                ],
                "contact_language": "en",
                "ignored": "value",
            }
        ) == {
            "additional_contact_email_addresses": ["a@example.com", "b@example.com"],
            "contact_language": "en",
        }

    def test_omitted_application_details_only_reads_account_state(self):
        client = Mock()
        module = FakeModule(
            {
                "additional_contact_email_addresses": [],
                "contact_language": "en",
                "mail_type": "transactional",
                "use_case_description": None,
                "website_url": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(
                plugin,
                "get_account",
                return_value={"details": {}, "production_access_enabled": False},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertFalse(raised.exception.values["changed"])
        require_methods.assert_called_once_with(module, client, "SESv2", {"get_account": ()})
        client.put_account_details.assert_not_called()

    def test_rejects_more_than_four_contact_addresses(self):
        module = FakeModule(
            {"additional_contact_email_addresses": [f"contact-{index}@example.com" for index in range(5)]}
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("at most 4", raised.exception.values["msg"])

    def test_rejects_blank_application_details_before_api_calls(self):
        for use_case_description, website_url in (
            (" ", "https://example.com"),
            ("example", " "),
        ):
            module = FakeModule(
                {
                    "additional_contact_email_addresses": [],
                    "contact_language": "en",
                    "mail_type": "transactional",
                    "use_case_description": use_case_description,
                    "website_url": website_url,
                }
            )
            with (
                self.subTest(website_url=website_url),
                patch.object(plugin, "AnsibleAWSModule", return_value=module),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.main()

            self.assertIn("non-empty strings", raised.exception.values["msg"])

    def test_successful_request_returns_refreshed_account_status(self):
        client = Mock()
        module = FakeModule(
            {
                "additional_contact_email_addresses": [],
                "contact_language": "en",
                "mail_type": "transactional",
                "use_case_description": "Production email",
                "website_url": "https://example.com",
            },
            client=client,
        )
        account = {
            "details": {"review_details": {"status": "PENDING"}},
            "production_access_enabled": False,
            "sending_enabled": True,
        }
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "get_account", return_value=account) as get_account,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertTrue(raised.exception.values["changed"])
        self.assertTrue(raised.exception.values["account"]["sending_enabled"])
        self.assertFalse(raised.exception.values["account"]["production_access_enabled"])
        self.assertEqual(get_account.call_count, 2)


def test_check_mode_preserves_observed_production_access():
    client = Mock()
    module = FakeModule(
        {
            "additional_contact_email_addresses": [],
            "contact_language": "en",
            "mail_type": "transactional",
            "use_case_description": "Production email",
            "website_url": "https://example.com",
        },
        client=client,
        check_mode=True,
    )
    account = {"details": {"review_details": {"status": "PENDING"}}, "production_access_enabled": False}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_account", return_value=account),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    assert result.value.values["changed"] is True
    assert result.value.values["account"]["production_access_enabled"] is False
    assert result.value.values["account"]["details"]["review_details"] == {"status": "PENDING"}
    client.put_account_details.assert_not_called()
