from unittest.mock import Mock, call, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_sender_id_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_documents_shape,
    assert_module_contract,
    documented_returns,
)

ARN = "arn:aws:sms-voice:us-east-1:123456789012:sender-id/EXAMPLE/DE"


def params(**overrides):
    values = {"filters": None, "max_results": None, "owner": None, "sender_ids": None}
    values.update(overrides)
    return values


def not_found():
    return plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribeSenderIds",
    )


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["owner", "sender_ids"]]
    assert "default" not in options["argument_spec"]["owner"]
    assert options["argument_spec"]["sender_ids"]["options"] == {
        "iso_country_code": {"required": True, "type": "str"},
        "sender_id": {"required": True, "type": "str"},
    }


def test_documented_returns_cover_the_sdk_shape():
    assert_documents_shape(
        documented_returns(plugin)["sender_ids"]["contains"], "pinpoint-sms-voice-v2", "SenderIdInformation"
    )


def test_listing_without_owner_sends_no_owner():
    # Owner requires botocore 1.35.26, so it is sent, and checked, only when the caller sets it.
    client = Mock()
    module = FakeModule(params(), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]) as query_list,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert query_list.call_args.kwargs == {}
    assert require.call_args_list == [
        call(module, client, "Pinpoint SMS Voice V2", {"describe_sender_ids": ("MaxResults", "NextToken")})
    ]
    assert raised.value.values == {"changed": False, "sender_ids": []}


def test_listing_with_owner_filters_and_max_results():
    client = Mock()
    module = FakeModule(
        params(filters={"iso-country-code": "DE", "registered": False}, max_results=10, owner="SELF"),
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]) as query_list,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query_list.call_args.kwargs == {
        "Filters": [
            {"Name": "iso-country-code", "Values": ["DE"]},
            {"Name": "registered", "Values": ["false"]},
        ],
        "MaxResults": 10,
        "Owner": "SELF",
    }
    assert require.call_args.args[3] == {"describe_sender_ids": ("MaxResults", "Owner", "Filters", "NextToken")}


def test_sender_ids_are_described_one_at_a_time_and_missing_ones_omitted():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Team", "Value": "Ops"}]}
    module = FakeModule(
        params(
            sender_ids=[
                {"sender_id": "MISSING", "iso_country_code": "DE"},
                {"sender_id": "EXAMPLE", "iso_country_code": "DE"},
            ]
        ),
        client=client,
    )
    found = {"IsoCountryCode": "DE", "SenderId": "EXAMPLE", "SenderIdArn": ARN, "MessageTypes": ["TRANSACTIONAL"]}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin, "paginated_query_with_retries", side_effect=[not_found(), {"SenderIds": [found]}]
        ) as query,
        patch.object(plugin, "query_list") as query_list,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [item.kwargs for item in query.call_args_list] == [
        {"SenderIds": [{"IsoCountryCode": "DE", "SenderId": "MISSING"}]},
        {"SenderIds": [{"IsoCountryCode": "DE", "SenderId": "EXAMPLE"}]},
    ]
    query_list.assert_not_called()
    assert require.call_args_list == [
        call(
            module, client, "Pinpoint SMS Voice V2", {"describe_sender_ids": ("SenderIds", "MaxResults", "NextToken")}
        ),
        call(module, client, "Pinpoint SMS Voice V2", {"list_tags_for_resource": ("ResourceArn",)}),
    ]
    assert raised.value.values == {
        "changed": False,
        "sender_ids": [
            {
                "iso_country_code": "DE",
                "message_types": ["TRANSACTIONAL"],
                "sender_id": "EXAMPLE",
                "sender_id_arn": ARN,
                "tags": {"Team": "Ops"},
            }
        ],
    }


def test_only_missing_sender_ids_return_empty_results():
    module = FakeModule(params(sender_ids=[{"sender_id": "MISSING", "iso_country_code": "DE"}]))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=not_found()),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["sender_ids"] == []


SHARED_ARN = "arn:aws:sms-voice:us-east-1:210987654321:sender-id/EXAMPLE/DE"


def test_only_exact_repeats_are_removed_from_requests():
    # One name and country can belong to several accounts, so a local ID and ARNs of other accounts all stay.
    assert plugin.unique_sender_ids(
        [
            {"sender_id": "EXAMPLE", "iso_country_code": "DE"},
            {"sender_id": ARN, "iso_country_code": "DE"},
            {"sender_id": SHARED_ARN, "iso_country_code": "DE"},
            {"sender_id": "EXAMPLE", "iso_country_code": "DE"},
            {"sender_id": "EXAMPLE", "iso_country_code": "FR"},
        ]
    ) == [
        {"IsoCountryCode": "DE", "SenderId": "EXAMPLE"},
        {"IsoCountryCode": "DE", "SenderId": ARN},
        {"IsoCountryCode": "DE", "SenderId": SHARED_ARN},
        {"IsoCountryCode": "FR", "SenderId": "EXAMPLE"},
    ]


def test_same_named_sender_ids_of_different_accounts_are_all_returned():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    module = FakeModule(
        params(
            sender_ids=[
                {"sender_id": "EXAMPLE", "iso_country_code": "DE"},
                {"sender_id": ARN, "iso_country_code": "DE"},
                {"sender_id": SHARED_ARN, "iso_country_code": "DE"},
            ]
        ),
        client=client,
    )
    own = {"IsoCountryCode": "DE", "SenderId": "EXAMPLE", "SenderIdArn": ARN}
    shared = {"IsoCountryCode": "DE", "SenderId": "EXAMPLE", "SenderIdArn": SHARED_ARN}
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=[{"SenderIds": [own]}, {"SenderIds": [own]}, {"SenderIds": [shared]}],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert query.call_count == 3
    # The local sender ID, found by its ID and by its ARN, is returned once.
    assert [sender_id["sender_id_arn"] for sender_id in raised.value.values["sender_ids"]] == [ARN, SHARED_ARN]


def test_id_lookup_fails_on_other_errors():
    denied = plugin.ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "DescribeSenderIds")
    module = FakeModule(params(sender_ids=[{"sender_id": "EXAMPLE", "iso_country_code": "DE"}]))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", side_effect=denied),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Unable to describe Pinpoint SMS Voice V2 sender ID EXAMPLE in DE"


@pytest.mark.parametrize("response", [[], {"SenderIds": "invalid"}, {"SenderIds": None}])
def test_id_lookup_rejects_malformed_response(response):
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=response),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.describe_sender_ids_by_id(
            FakeModule({}), Mock(), {"SenderIds": [{"IsoCountryCode": "DE", "SenderId": "EXAMPLE"}]}
        )

    assert raised.value.values["msg"] == "AWS returned malformed Pinpoint SMS Voice V2 sender ID data"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"max_results": 0}, "max_results must be between 1 and 100"),
        ({"max_results": 101}, "max_results must be between 1 and 100"),
        ({"filters": {str(index): "x" for index in range(21)}}, "filters must contain at most 20 entries"),
        (
            {"sender_ids": [{"sender_id": f"ID{index}", "iso_country_code": "DE"} for index in range(6)]},
            "sender_ids must contain at most 5 entries",
        ),
        ({"sender_ids": [{"sender_id": " ", "iso_country_code": "DE"}]}, "sender_ids sender_id must not be empty"),
        (
            {"sender_ids": [{"sender_id": "EXAMPLE", "iso_country_code": None}]},
            "sender_ids iso_country_code must not be empty",
        ),
    ],
)
def test_rejects_invalid_input_before_any_aws_call(overrides, message):
    module = FakeModule(params(**overrides))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(module, "client") as connect,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == message
    connect.assert_not_called()


def test_repeated_sender_ids_count_once_against_the_limit():
    module = FakeModule(params(sender_ids=[{"sender_id": "EXAMPLE", "iso_country_code": "DE"}] * 6))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"SenderIds": []}) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_count == 1


def test_listing_error_is_reported():
    client = Mock()
    client.can_paginate.return_value = True
    module = FakeModule(params(), client=client)
    denied = plugin.ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "DescribeSenderIds")
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch(
            "ansible_collections.linuxhq.aws.plugins.module_utils.sdk.paginated_query_with_retries", side_effect=denied
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Unable to describe Pinpoint SMS Voice V2 sender IDs"


def test_sender_id_released_while_listing_tags_is_omitted():
    client = Mock()
    client.list_tags_for_resource.side_effect = not_found()
    module = FakeModule(params(), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin, "query_list", return_value=[{"IsoCountryCode": "DE", "SenderId": "EXAMPLE", "SenderIdArn": ARN}]
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["sender_ids"] == []


def test_rejects_malformed_sender_id():
    module = FakeModule(params())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"SenderIdArn": ARN}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "AWS returned malformed Pinpoint SMS Voice V2 sender ID data"


def test_rejects_malformed_tags():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": "invalid"}
    module = FakeModule(params(), client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin, "query_list", return_value=[{"IsoCountryCode": "DE", "SenderId": "EXAMPLE", "SenderIdArn": ARN}]
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "malformed tags" in raised.value.values["msg"]
