from unittest.mock import Mock, call, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_number_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["mutually_exclusive"] == [["owner", "phone_number_ids"]]
    assert "default" not in options["argument_spec"]["owner"]


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
        patch.object(plugin, "paginated_query_with_retries", return_value={"PhoneNumbers": []}) as query,
        patch.object(plugin, "query_list") as query_list,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_args.kwargs == {"PhoneNumberIds": ["phone-1"]}
    query_list.assert_not_called()


def test_missing_ids_are_omitted_from_results():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "missing"}},
        "DescribePhoneNumbers",
    )
    client = Mock()
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
            plugin,
            "paginated_query_with_retries",
            side_effect=[missing, {"PhoneNumbers": [{"PhoneNumberId": "phone-1"}]}],
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
    missing = plugin.ClientError(
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
        patch.object(plugin, "paginated_query_with_retries", side_effect=missing),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["phone_number_ids"] == []
    assert raised.value.values["phone_numbers"] == []


def test_id_lookup_fails_on_other_errors():
    denied = plugin.ClientError(
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
        patch.object(plugin, "paginated_query_with_retries", side_effect=denied),
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


def test_rejects_max_results_above_provider_limit():
    module = FakeModule(
        {
            "filters": None,
            "max_results": 101,
            "owner": "SELF",
            "phone_number_ids": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "max_results must be between 1 and 100"


def test_rejects_provider_list_limits():
    cases = [
        (
            {
                "filters": {str(index): "x" for index in range(21)},
                "max_results": None,
                "owner": None,
                "phone_number_ids": None,
            },
            "filters must contain at most 20 entries",
        ),
        (
            {
                "filters": None,
                "max_results": None,
                "owner": None,
                "phone_number_ids": [f"phone-{index}" for index in range(6)],
            },
            "phone_number_ids must contain at most 5 entries",
        ),
    ]
    for params, message in cases:
        module = FakeModule(params)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert raised.value.values["msg"] == message


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


def test_rejects_malformed_phone_number():
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
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"PhoneNumberArn": "arn:phone"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "malformed" in raised.value.values["msg"]


def test_rejects_malformed_tags():
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": "invalid"}
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
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"PhoneNumberArn": "arn:phone", "PhoneNumberId": "phone-1"}],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "malformed tags" in raised.value.values["msg"]
