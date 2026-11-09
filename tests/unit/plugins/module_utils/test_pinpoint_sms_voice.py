from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.pinpoint_sms_voice import (
    is_last_phone_number,
    is_phone_number_reference,
    last_phone_number_message,
    list_tags,
    predicted_origination_identity,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail

ARN = "arn:aws:sms-voice:us-east-1:123456789012:pool/pool-1"
MISSING = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}}, "ListTagsForResource")


def test_list_tags_returns_the_tag_list():
    tags = [{"Key": "Name", "Value": "example"}]
    client = Mock(list_tags_for_resource=Mock(return_value={"Tags": tags}))

    assert list_tags(client, FakeModule({}), ARN, "pool") == tags
    client.list_tags_for_resource.assert_called_once_with(ResourceArn=ARN, aws_retry=True)


def test_list_tags_defaults_missing_tags_to_empty():
    client = Mock(list_tags_for_resource=Mock(return_value={}))

    assert list_tags(client, FakeModule({}), ARN, "pool") == []


def test_list_tags_returns_none_for_a_missing_resource_when_allowed():
    client = Mock(list_tags_for_resource=Mock(side_effect=MISSING))

    assert list_tags(client, FakeModule({}), ARN, "pool", missing_ok=True) is None


@pytest.mark.parametrize("changed", [False, True])
def test_list_tags_fails_for_a_missing_resource_by_default(changed):
    client = Mock(list_tags_for_resource=Mock(side_effect=MISSING))

    with pytest.raises(ModuleFail) as raised:
        list_tags(client, FakeModule({}), ARN, "phone number", changed=changed)

    assert raised.value.values == {
        "changed": changed,
        "msg": f"Unable to list tags for Pinpoint SMS Voice V2 phone number {ARN}",
    }


@pytest.mark.parametrize("response", [None, {"Tags": [{"Key": "Name"}]}])
def test_list_tags_rejects_malformed_tags(response):
    client = Mock(list_tags_for_resource=Mock(return_value=response))

    with pytest.raises(ModuleFail) as raised:
        list_tags(client, FakeModule({}), ARN, "pool", changed=True)

    assert raised.value.values == {
        "changed": True,
        "msg": f"AWS returned malformed tags for Pinpoint SMS Voice V2 pool {ARN}",
    }


PHONE_ARN = "arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-1"
SENDER_ARN = "arn:aws:sms-voice:us-east-1:123456789012:sender-id/sender-1/US"


@pytest.mark.parametrize(
    ("origination_identity", "iso_country_code", "expected"),
    [
        (
            PHONE_ARN,
            "US",
            {"IsoCountryCode": "US", "OriginationIdentity": "phone-1", "OriginationIdentityArn": PHONE_ARN},
        ),
        (
            SENDER_ARN,
            "US",
            {"IsoCountryCode": "US", "OriginationIdentity": "sender-1", "OriginationIdentityArn": SENDER_ARN},
        ),
        (
            SENDER_ARN,
            None,
            {"IsoCountryCode": "US", "OriginationIdentity": "sender-1", "OriginationIdentityArn": SENDER_ARN},
        ),
        # An ARN without the sender-id/<SenderId>/<country> form is left for AWS to reject.
        (
            "arn:aws:sms-voice:us-east-1:123456789012:sender-id/sender-1",
            None,
            {"OriginationIdentity": "arn:aws:sms-voice:us-east-1:123456789012:sender-id/sender-1"},
        ),
        ("phone-1", "US", {"IsoCountryCode": "US", "OriginationIdentity": "phone-1"}),
        ("sender-1", None, {"OriginationIdentity": "sender-1"}),
    ],
)
def test_predicted_origination_identity_matches_the_associated_identity(
    origination_identity, iso_country_code, expected
):
    assert predicted_origination_identity(origination_identity, iso_country_code) == expected


@pytest.mark.parametrize(
    ("origination_identity", "expected"),
    [
        ("phone-720f0a64a09b4e1ebdcc8273b27bd3fc", True),
        (PHONE_ARN, True),
        # A sender ID has at most 11 characters, so even one that starts with "phone-" is not a phone number ID.
        ("phone-1", False),
        ("phone-12345", False),
        ("sender-1", False),
        (SENDER_ARN, False),
        ("phone-720F0A64A09B4E1EBDCC8273B27BD3FC", False),
        ("arn:aws:sms-voice:us-east-1:123456789012:phone-number", False),
    ],
)
def test_phone_number_reference_matches_only_phone_number_ids_and_arns(origination_identity, expected):
    assert is_phone_number_reference(origination_identity) is expected


PHONE_ITEM = {"OriginationIdentity": "phone-1", "OriginationIdentityArn": PHONE_ARN, "PhoneNumber": "+12065550100"}
SENDER_ITEM = {"OriginationIdentity": "sender-1", "OriginationIdentityArn": SENDER_ARN}
OTHER_SENDER_ITEM = {"OriginationIdentity": "sender-2"}


@pytest.mark.parametrize(
    ("originations", "identities", "expected"),
    [
        ([PHONE_ITEM], ("phone-1",), True),
        ([PHONE_ITEM], (PHONE_ARN,), True),
        ([PHONE_ITEM], ("phone-2",), False),
        ([SENDER_ITEM], ("sender-1",), True),
        ([SENDER_ITEM], (SENDER_ARN,), True),
        ([SENDER_ITEM, OTHER_SENDER_ITEM], ("sender-1",), False),
        # Live: AWS accepts removing a phone number while a sender ID remains in the pool.
        ([PHONE_ITEM, SENDER_ITEM], ("phone-1",), False),
        ([PHONE_ITEM, SENDER_ITEM], ("sender-1",), False),
        ([], ("phone-1",), False),
    ],
)
def test_is_last_phone_number_matches_only_a_pools_sole_identity(originations, identities, expected):
    assert is_last_phone_number(originations, identities) is expected


def test_last_phone_number_message_names_the_identity_type():
    assert last_phone_number_message("phone-1", "pool-1").startswith(
        "Phone number phone-1 is the last phone number in Pinpoint SMS Voice V2 pool pool-1, "
    )
    assert last_phone_number_message("sender-1", "pool-1", False).startswith(
        "Origination identity sender-1 is the last origination identity in Pinpoint SMS Voice V2 pool pool-1, "
    )
