from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ses_sandbox as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

DETAILS = {
    "additional_contact_email_addresses": ["existing@example.com"],
    "contact_language": "EN",
    "mail_type": "TRANSACTIONAL",
    "use_case_description": "Production email",
    "website_url": "https://example.com",
}


def params(**overrides):
    values = {
        "additional_contact_email_addresses": [],
        "contact_language": None,
        "mail_type": None,
        "use_case_description": "Production email",
        "website_url": "https://example.com",
    }
    values.update(overrides)
    return values


def run(module, *accounts):
    """Run main() with get_account returning each account in turn."""
    module.warn = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "get_account", side_effect=list(accounts)) as get_account,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods, get_account


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    spec = captured["argument_spec"]
    assert captured["supports_check_mode"]
    assert "required_together" not in captured
    assert "default" not in spec["contact_language"]
    assert "default" not in spec["mail_type"]
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_account_details_are_deduplicated_and_sorted():
    assert plugin.comparable_details(
        {
            "additional_contact_email_addresses": ["b@example.com", "a@example.com", "b@example.com"],
            "contact_language": "en",
            "ignored": "value",
        }
    ) == {"additional_contact_email_addresses": ["a@example.com", "b@example.com"], "contact_language": "en"}


@pytest.mark.parametrize("check_mode", [False, True])
def test_omitted_contacts_preserve_existing_addresses_without_update(check_mode):
    client = Mock()
    account = {"details": DETAILS, "production_access_enabled": True}
    result, _require, _get = run(FakeModule(params(), client=client, check_mode=check_mode), account)

    assert not result.values["changed"]
    assert result.values["account"] == account
    client.put_account_details.assert_not_called()


def test_omitted_website_only_reads_account_state():
    client = Mock()
    result, require_client_methods, _get = run(
        FakeModule(params(use_case_description=None, website_url=None), client=client),
        {"details": {}, "production_access_enabled": False},
    )

    assert not result.values["changed"]
    assert require_client_methods.call_args.args[3] == {"get_account": ()}
    client.put_account_details.assert_not_called()


def test_rejects_more_than_four_contact_addresses():
    result, _require, _get = run(
        FakeModule(params(additional_contact_email_addresses=[f"contact-{index}@example.com" for index in range(5)]))
    )

    assert "at most 4" in result.values["msg"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"website_url": " "}, "website_url must be a non-empty string"),
        ({"use_case_description": " "}, "use_case_description must be a non-empty string"),
    ],
)
def test_rejects_blank_application_details_before_api_calls(overrides, message):
    result, _require, get_account = run(FakeModule(params(**overrides)))

    assert result.values["msg"] == message
    get_account.assert_not_called()


def test_website_url_alone_submits_a_request():
    client = Mock()
    result, _require, _get = run(
        FakeModule(params(use_case_description=None), client=client),
        {"details": {}, "production_access_enabled": False},
        {"details": {"review_details": {"status": "PENDING"}}, "production_access_enabled": False},
    )

    assert result.values["changed"]
    client.put_account_details.assert_called_once_with(
        ProductionAccessEnabled=True,
        ContactLanguage="EN",
        MailType="TRANSACTIONAL",
        WebsiteURL="https://example.com",
        aws_retry=True,
    )


def test_successful_request_returns_refreshed_account_status():
    client = Mock()
    refreshed = {
        "details": {"review_details": {"status": "PENDING"}},
        "production_access_enabled": False,
        "sending_enabled": True,
    }
    result, _require, get_account = run(
        FakeModule(params(), client=client), {"details": {}, "production_access_enabled": False}, refreshed
    )

    assert result.values["changed"]
    assert result.values["account"] == refreshed
    assert get_account.call_count == 2


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("status", ["PENDING", "DENIED", "FAILED"])
def test_reviewed_request_with_same_details_is_not_resubmitted(status, check_mode):
    client = Mock()
    details = dict(DETAILS, review_details={"status": status})
    module = FakeModule(params(), client=client, check_mode=check_mode)
    result, _require, _get = run(module, {"details": details, "production_access_enabled": False})

    assert not result.values["changed"]
    client.put_account_details.assert_not_called()
    if status == "PENDING":
        module.warn.assert_not_called()
    else:
        module.warn.assert_called_once_with(
            f"AWS Simple Email Service production access request was {status}; "
            "change the account details to submit a new request"
        )


def test_denied_request_with_new_details_is_resubmitted():
    client = Mock()
    details = dict(DETAILS, review_details={"status": "DENIED"})
    result, _require, _get = run(
        FakeModule(params(website_url="https://example.org"), client=client),
        {"details": details, "production_access_enabled": False},
        {"details": details, "production_access_enabled": False},
    )

    assert result.values["changed"]
    assert client.put_account_details.call_args.kwargs["WebsiteURL"] == "https://example.org"


def test_use_case_description_does_not_trigger_a_request():
    client = Mock()
    details = dict(DETAILS, use_case_description='"Production email"', review_details={"status": "DENIED"})
    result, _require, _get = run(
        FakeModule(params(), client=client), {"details": details, "production_access_enabled": False}
    )

    assert not result.values["changed"]
    client.put_account_details.assert_not_called()


def test_omitted_choices_keep_current_values():
    client = Mock()
    details = dict(DETAILS, contact_language="JA", mail_type="MARKETING")
    result, _require, _get = run(
        FakeModule(params(website_url="https://example.org"), client=client),
        {"details": details, "production_access_enabled": True},
        {"details": details, "production_access_enabled": True},
    )

    assert result.values["changed"]
    request = client.put_account_details.call_args.kwargs
    assert request["ContactLanguage"] == "JA"
    assert request["MailType"] == "MARKETING"


def test_supplied_choices_are_converged():
    client = Mock()
    result, _require, _get = run(
        FakeModule(params(contact_language="ja", mail_type="marketing"), client=client),
        {"details": DETAILS, "production_access_enabled": True},
        {"details": DETAILS, "production_access_enabled": True},
    )

    assert result.values["changed"]
    request = client.put_account_details.call_args.kwargs
    assert request["ContactLanguage"] == "JA"
    assert request["MailType"] == "MARKETING"


def test_conflict_is_reported_as_unchanged():
    client = Mock()
    client.put_account_details.side_effect = ClientError(
        {"Error": {"Code": "ConflictException", "Message": "busy"}}, "PutAccountDetails"
    )
    module = FakeModule(params(), client=client)
    result, _require, _get = run(module, {"details": {}, "production_access_enabled": False})

    assert not result.values["changed"]
    module.warn.assert_called_once_with("AWS Simple Email Service account details request is already in progress")


def test_check_mode_preserves_observed_production_access():
    client = Mock()
    account = {"details": {}, "production_access_enabled": False}
    result, _require, _get = run(FakeModule(params(), client=client, check_mode=True), account)

    assert result.values["changed"] is True
    assert result.values["account"]["production_access_enabled"] is False
    assert result.values["account"]["details"]["website_url"] == "https://example.com"
    client.put_account_details.assert_not_called()
