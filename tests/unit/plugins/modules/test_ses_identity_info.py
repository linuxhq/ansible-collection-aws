from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ses_identity_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
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
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["mutually_exclusive"] == [["identity_type", "name"]]
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_named_identity_skips_listing_and_returns_dkim_and_verification_token():
    ses, sesv2 = clients(
        {"example.com": {"DkimAttributes": {"Tokens": ["a", "b", "c"]}, "VerifiedForSendingStatus": True}},
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
    ses, sesv2 = clients({"user@example.com": {}}, {"user@example.com": {"VerificationStatus": "Success"}})
    result, _require, _query = run(FakeModule({"identity_type": None, "name": "user@example.com"}), ses, sesv2)

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
    ses, sesv2 = clients({name: {} for name in names})
    module = FakeModule({"identity_type": "Domain", "name": None})
    _result, require_client_methods, _query = run(module, ses, sesv2, names)

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
            "list_identities": ("IdentityType", "MaxItems", "NextToken"),
        },
    )


def test_rejects_invalid_verification_attributes():
    ses, sesv2 = clients({"example.com": {}})
    ses.get_identity_verification_attributes.return_value = {"VerificationAttributes": []}
    result, _require, _query = run(FakeModule({"identity_type": None, "name": "example.com"}), ses, sesv2)

    assert result.values["msg"] == "AWS SES returned invalid identity verification attributes"


def test_empty_name_is_rejected():
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule({"identity_type": None, "name": ""})),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "name must not be empty"


@pytest.mark.parametrize("names", [[None], None])
def test_validate_identity_names_rejects_invalid_names(names):
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_identity_names(FakeModule({}), names)

    assert raised.value.values["msg"] == "AWS SES returned an invalid identity name"


@pytest.mark.parametrize(
    ("details", "message"),
    [
        ([], "invalid details"),
        ({"Tags": [{"Key": "missing-value"}]}, "invalid tags"),
        ({"Policies": []}, "invalid policies"),
    ],
)
def test_validate_identity_details_rejects_invalid_details(details, message):
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_identity_details(FakeModule({}), details, "example.com")

    assert message in raised.value.values["msg"]
