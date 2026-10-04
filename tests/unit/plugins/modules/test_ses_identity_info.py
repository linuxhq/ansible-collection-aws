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


def run(module, clients, names=None):
    module.client = Mock(side_effect=clients)
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


def test_named_identity_skips_listing_and_returns_dkim_tokens():
    sesv2 = Mock(
        get_email_identity=Mock(
            return_value={"DkimAttributes": {"Tokens": ["a", "b", "c"]}, "VerifiedForSendingStatus": True}
        )
    )
    module = FakeModule({"identity_type": None, "name": "example.com"})
    result, require_client_methods, query_list = run(module, [sesv2])

    query_list.assert_not_called()
    require_client_methods.assert_called_once_with(module, sesv2, "SESv2", {"get_email_identity": ("EmailIdentity",)})
    identity = result.values["identities"][0]
    assert identity["name"] == "example.com"
    assert identity["dkim_attributes"]["tokens"] == ["a", "b", "c"]


def test_missing_named_identity_returns_empty_list():
    sesv2 = Mock(
        get_email_identity=Mock(
            side_effect=plugin.ClientError(
                {"Error": {"Code": "NotFoundException", "Message": "gone"}}, "GetEmailIdentity"
            )
        )
    )
    result, _require, _query = run(FakeModule({"identity_type": None, "name": "missing.com"}), [sesv2])

    assert result.values["identities"] == []


def test_listing_requires_pagination_parameters():
    ses = Mock()
    sesv2 = Mock()
    module = FakeModule({"identity_type": "Domain", "name": None})
    _result, require_client_methods, _query = run(module, [ses, sesv2], [])

    require_client_methods.assert_any_call(
        module, ses, "SES", {"list_identities": ("IdentityType", "MaxItems", "NextToken")}
    )


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
