from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ses_identity_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_documents_shape,
    assert_module_contract,
    documented_returns,
)


def clients(identities=None, verification=None):
    """Return SES v1 and SESv2 clients for the given identity details and verification attributes."""
    ses = Mock(get_identity_verification_attributes=Mock(return_value={"VerificationAttributes": verification or {}}))
    details = identities or {}
    sesv2 = Mock(get_email_identity=Mock(side_effect=lambda EmailIdentity, aws_retry: dict(details[EmailIdentity])))
    return ses, sesv2


def run(module, ses, sesv2, names=None):
    module.client = Mock(side_effect=[ses, sesv2])
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=names) as query_list,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods, query_list


def test_module_contract():
    captured = assert_module_contract(plugin)

    assert captured["mutually_exclusive"] == [["identity_type", "name"]]


def test_named_identity_skips_listing_and_returns_dkim_and_verification_token():
    ses, sesv2 = clients(
        {
            "example.com": {
                "DkimAttributes": {"Tokens": ["a", "b", "c"]},
                "IdentityType": "DOMAIN",
                "VerifiedForSendingStatus": True,
            }
        },
        {"example.com": {"VerificationStatus": "Success", "VerificationToken": "txt-token"}},
    )
    module = FakeModule({"identity_type": None, "name": "example.com"})
    result, require_client_methods, query_list = run(module, ses, sesv2)

    query_list.assert_not_called()
    require_client_methods.assert_any_call(
        module, ses, "SES", {"get_identity_verification_attributes": ("Identities",)}
    )
    require_client_methods.assert_any_call(module, sesv2, "SESv2", {"get_email_identity": ("EmailIdentity",)})
    identity = result.values["identities"][0]
    assert identity["name"] == "example.com"
    assert identity["dkim_attributes"]["tokens"] == ["a", "b", "c"]
    assert identity["verification_token"] == "txt-token"
    ses.get_identity_verification_attributes.assert_called_once_with(Identities=["example.com"], aws_retry=True)


def test_identity_without_verification_token_omits_it():
    ses, sesv2 = clients(
        {"example.com": {"IdentityType": "DOMAIN"}}, {"example.com": {"VerificationStatus": "Success"}}
    )
    result, _require, _query = run(FakeModule({"identity_type": None, "name": "example.com"}), ses, sesv2)

    assert "verification_token" not in result.values["identities"][0]


def test_missing_named_identity_returns_empty_list_without_token_lookup():
    ses = Mock()
    sesv2 = Mock(
        get_email_identity=Mock(
            side_effect=plugin.ClientError(
                {"Error": {"Code": "NotFoundException", "Message": "gone"}}, "GetEmailIdentity"
            )
        )
    )
    result, _require, _query = run(FakeModule({"identity_type": None, "name": "missing.com"}), ses, sesv2)

    assert result.values["identities"] == []
    ses.get_identity_verification_attributes.assert_not_called()


def test_verification_tokens_are_requested_in_batches_of_one_hundred():
    names = [f"d{index}.com" for index in range(150)]
    ses, sesv2 = clients({name: {"IdentityType": "DOMAIN"} for name in names})
    module = FakeModule({"identity_type": "Domain", "name": None})
    _result, require_client_methods, query_list = run(module, ses, sesv2, names)

    assert [len(call.kwargs["Identities"]) for call in ses.get_identity_verification_attributes.call_args_list] == [
        100,
        50,
    ]
    require_client_methods.assert_any_call(
        module,
        ses,
        "SES",
        {
            "get_identity_verification_attributes": ("Identities",),
            "list_identities": ("NextToken", "IdentityType"),
        },
    )
    query_list.assert_called_once_with(
        module, ses, "list_identities", "Identities", "Unable to list AWS SES identities", IdentityType="Domain"
    )


def test_verification_tokens_are_requested_only_for_domains():
    identities = {
        "example.com": {"IdentityType": "DOMAIN"},
        "managed.example.com": {"IdentityType": "MANAGED_DOMAIN"},
        "user@example.com": {"IdentityType": "EMAIL_ADDRESS"},
    }
    ses, sesv2 = clients(identities, {"example.com": {"VerificationToken": "txt-token"}})
    result, _require, _query = run(FakeModule({"identity_type": None, "name": None}), ses, sesv2, list(identities))

    ses.get_identity_verification_attributes.assert_called_once_with(Identities=["example.com"], aws_retry=True)
    assert [identity.get("verification_token") for identity in result.values["identities"]] == ["txt-token", None, None]


def test_empty_name_lists_every_identity():
    ses, sesv2 = clients({"user@example.com": {"IdentityType": "EMAIL_ADDRESS"}})
    module = FakeModule({"identity_type": None, "name": ""})
    result, require_client_methods, query_list = run(module, ses, sesv2, ["user@example.com"])

    # Without identity_type, ListIdentities is neither sent nor gated on IdentityType.
    require_client_methods.assert_any_call(
        module,
        ses,
        "SES",
        {"get_identity_verification_attributes": ("Identities",), "list_identities": ("NextToken",)},
    )
    query_list.assert_called_once_with(
        module, ses, "list_identities", "Identities", "Unable to list AWS SES identities"
    )
    assert [identity["name"] for identity in result.values["identities"]] == ["user@example.com"]


def test_return_documents_every_get_email_identity_field():
    contains = documented_returns(plugin)["identities"]["contains"]

    assert_documents_shape(contains, "sesv2", "GetEmailIdentityResponse")
    assert {"name", "verification_token"} <= set(contains)
