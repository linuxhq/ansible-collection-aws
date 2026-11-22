from unittest.mock import Mock, call, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import pinpoint_sms_voice
from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_number_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_documents_shape,
    assert_module_contract,
    documented_returns,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["owner", "phone_number_ids"]]
    assert "default" not in options["argument_spec"]["owner"]


def test_documented_returns_cover_the_sdk_shape():
    # Each phone number is a DescribePhoneNumbers item with every member AWS sends.
    assert_documents_shape(
        documented_returns(plugin)["phone_numbers"]["contains"], "pinpoint-sms-voice-v2", "PhoneNumberInformation"
    )


def test_ids_do_not_send_the_implicit_owner():
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": None,
            "phone_number_ids": ["phone-1"],
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(pinpoint_sms_voice, "paginated_query_with_retries", return_value={"PhoneNumbers": []}) as query,
        patch.object(plugin, "query_list") as query_list,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_args.kwargs == {"PhoneNumberIds": ["phone-1"]}
    query_list.assert_not_called()


@pytest.mark.parametrize(
    ("ids", "expected"),
    [
        (
            ["phone-1", "arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-1", "phone-2"],
            ["arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-1", "phone-2"],
        ),
        (
            ["arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-1", "phone-1"],
            ["arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-1"],
        ),
    ],
)
def test_ids_and_arns_of_one_resource_are_described_once(ids, expected):
    module = FakeModule({"filters": None, "max_results": None, "owner": None, "phone_number_ids": ids})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(pinpoint_sms_voice, "paginated_query_with_retries", return_value={"PhoneNumbers": []}) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert [query_call.kwargs for query_call in query.call_args_list] == [
        {"PhoneNumberIds": [identifier]} for identifier in expected
    ]


def test_missing_ids_are_omitted_from_results():
    missing = pinpoint_sms_voice.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribePhoneNumbers",
    )
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule(
        {
            "filters": {"status": "ACTIVE"},
            "max_results": 10,
            "owner": None,
            "phone_number_ids": ["phone-missing", "phone-1"],
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            pinpoint_sms_voice,
            "paginated_query_with_retries",
            side_effect=[missing, {"PhoneNumbers": [{"PhoneNumberArn": "arn:phone", "PhoneNumberId": "phone-1"}]}],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [item.kwargs["PhoneNumberIds"] for item in query.call_args_list] == [["phone-missing"], ["phone-1"]]
    assert query.call_args.kwargs["MaxResults"] == 10
    assert query.call_args.kwargs["Filters"] == [{"Name": "status", "Values": ["ACTIVE"]}]
    assert raised.value.values["phone_number_ids"] == ["phone-1"]
    assert raised.value.values["changed"] is False


def test_only_missing_ids_return_empty_results():
    missing = pinpoint_sms_voice.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribePhoneNumbers",
    )
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": None,
            "phone_number_ids": ["phone-missing"],
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(pinpoint_sms_voice, "paginated_query_with_retries", side_effect=missing),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["phone_number_ids"] == []
    assert raised.value.values["phone_numbers"] == []


def test_id_lookup_fails_on_other_errors():
    denied = pinpoint_sms_voice.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "DescribePhoneNumbers",
    )
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": None,
            "phone_number_ids": ["phone-1"],
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(pinpoint_sms_voice, "paginated_query_with_retries", side_effect=denied),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Unable to describe Pinpoint SMS Voice V2 phone number phone-1"


def test_empty_result_does_not_require_tag_operations():
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": "SELF",
            "phone_number_ids": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_args.args[3] == {"describe_phone_numbers": ("Owner", "MaxResults", "NextToken")}


def test_more_than_five_ids_are_described_one_at_a_time():
    # Each ID is described in its own request, so the DescribePhoneNumbers limit of five IDs does not apply.
    phone_number_ids = [f"phone-{index}" for index in range(6)]
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule(
        {"filters": None, "max_results": None, "owner": None, "phone_number_ids": phone_number_ids},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            pinpoint_sms_voice,
            "paginated_query_with_retries",
            side_effect=[
                {"PhoneNumbers": [{"PhoneNumberArn": f"arn:phone/{phone_number_id}", "PhoneNumberId": phone_number_id}]}
                for phone_number_id in phone_number_ids
            ],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [item.kwargs["PhoneNumberIds"] for item in query.call_args_list] == [[item] for item in phone_number_ids]
    assert raised.value.values["phone_number_ids"] == phone_number_ids


def test_phone_numbers_are_enriched_with_tags():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Name", "Value": "primary"}]}
    module = FakeModule(
        {
            "filters": None,
            "max_results": None,
            "owner": "SELF",
            "phone_number_ids": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "query_list",
            return_value=[{"PhoneNumberArn": "arn:phone", "PhoneNumberId": "phone-1"}],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["phone_number_ids"] == ["phone-1"]
    assert raised.value.values["phone_numbers"][0]["tags"] == {"Name": "primary"}
    assert require.call_args_list == [
        call(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {
                "describe_phone_numbers": (
                    "Owner",
                    "MaxResults",
                    "NextToken",
                )
            },
        ),
        call(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {"list_tags_for_resource": ("ResourceArn",)},
        ),
    ]
