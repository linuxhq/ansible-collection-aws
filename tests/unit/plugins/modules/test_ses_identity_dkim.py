from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ses_identity_dkim as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

EASY = {"SigningAttributesOrigin": "AWS_SES", "SigningEnabled": True, "Status": "SUCCESS", "Tokens": ["a", "b", "c"]}


def params(**overrides):
    values = {"identity": "example.com", "signing_enabled": True}
    values.update(overrides)
    return values


def client_with(*attributes):
    """Return a client whose GetEmailIdentity returns each DKIM attributes dict in turn."""
    return Mock(get_email_identity=Mock(side_effect=[{"DkimAttributes": value} for value in attributes]))


def run(module):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["signing_enabled"] == {"default": True, "type": "bool"}
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


@pytest.mark.parametrize(
    ("identity", "message"),
    [("", "identity must not be empty"), ("user@example.com", "identity must be a domain name, not an email address")],
)
def test_rejects_invalid_identity(identity, message):
    result, _require = run(FakeModule(params(identity=identity), client=Mock()))

    assert result.values["msg"] == message


def test_enabled_easy_dkim_is_unchanged():
    client = client_with(EASY)
    result, _require = run(FakeModule(params(), client=client))

    assert not result.values["changed"]
    assert result.values["dkim_attributes"]["tokens"] == ["a", "b", "c"]
    client.put_email_identity_dkim_signing_attributes.assert_not_called()
    client.put_email_identity_dkim_attributes.assert_not_called()


@pytest.mark.parametrize(
    "current",
    [
        {"SigningEnabled": False, "Status": "NOT_STARTED"},
        {"SigningAttributesOrigin": "EXTERNAL", "SigningEnabled": True, "Tokens": []},
    ],
)
def test_easy_dkim_tokens_are_generated(current):
    client = client_with(current, EASY)
    result, _require = run(FakeModule(params(), client=client))

    assert result.values["changed"]
    assert result.values["dkim_attributes"]["tokens"] == ["a", "b", "c"]
    client.put_email_identity_dkim_signing_attributes.assert_called_once_with(
        EmailIdentity="example.com", SigningAttributesOrigin="AWS_SES", aws_retry=True
    )
    client.put_email_identity_dkim_attributes.assert_not_called()


def test_signing_is_enabled_when_generated_tokens_are_not_signing():
    client = client_with({"Status": "NOT_STARTED"}, dict(EASY, SigningEnabled=False), EASY)
    result, _require = run(FakeModule(params(), client=client))

    assert result.values["changed"]
    client.put_email_identity_dkim_attributes.assert_called_once_with(
        EmailIdentity="example.com", SigningEnabled=True, aws_retry=True
    )
    assert result.values["dkim_attributes"]["signing_enabled"] is True


def test_signing_is_disabled_without_generating_tokens():
    client = client_with(EASY, dict(EASY, SigningEnabled=False))
    result, _require = run(FakeModule(params(signing_enabled=False), client=client))

    assert result.values["changed"]
    client.put_email_identity_dkim_signing_attributes.assert_not_called()
    client.put_email_identity_dkim_attributes.assert_called_once_with(
        EmailIdentity="example.com", SigningEnabled=False, aws_retry=True
    )


def test_check_mode_predicts_generation_without_calling_aws():
    client = client_with({"Status": "NOT_STARTED"})
    result, _require = run(FakeModule(params(), client=client, check_mode=True))

    assert result.values["changed"]
    assert result.values["dkim_attributes"] == {
        "signing_attributes_origin": "AWS_SES",
        "signing_enabled": True,
        "status": "NOT_STARTED",
        "tokens": [],
    }
    client.put_email_identity_dkim_signing_attributes.assert_not_called()
    client.put_email_identity_dkim_attributes.assert_not_called()


def test_missing_identity_fails():
    client = Mock(
        get_email_identity=Mock(
            side_effect=ClientError({"Error": {"Code": "NotFoundException", "Message": "gone"}}, "GetEmailIdentity")
        )
    )
    result, _require = run(FakeModule(params(), client=client))

    assert result.values["msg"] == "AWS SES identity example.com does not exist"


def test_rejects_invalid_dkim_attributes():
    client = Mock(get_email_identity=Mock(return_value={"DkimAttributes": []}))
    result, _require = run(FakeModule(params(), client=client))

    assert result.values["msg"] == "AWS SES returned invalid DKIM attributes for identity example.com"
