from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_vpc_prefix_list_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_prefix_list_disappearing_during_entry_lookup_is_omitted():
    client = Mock()
    module = FakeModule(
        {"filters": None, "prefix_list_ids": ["pl-gone"], "target_version": None},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(
            plugin,
            "query_list",
            return_value=[{"PrefixListId": "pl-gone"}],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=plugin.ClientError(
                {
                    "Error": {
                        "Code": "InvalidPrefixListID.NotFound",
                        "Message": "gone",
                    }
                },
                "GetManagedPrefixListEntries",
            ),
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["prefix_lists"] == []
    assert require_methods.call_args_list[0].args == (
        module,
        client,
        "EC2",
        {
            "describe_managed_prefix_lists": (
                "Filters",
                "MaxResults",
                "NextToken",
            ),
        },
    )
    assert require_methods.call_args_list[1].args == (
        module,
        client,
        "EC2",
        {
            "get_managed_prefix_list_entries": (
                "MaxResults",
                "NextToken",
                "PrefixListId",
            ),
        },
    )


def test_sdk_validation_ignores_unused_filters():
    module = FakeModule(
        {"filters": None, "prefix_list_ids": None, "target_version": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require_methods.call_args.args[3]["describe_managed_prefix_lists"] == ("MaxResults", "NextToken")
    assert require_methods.call_count == 1


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["target_version"]["type"] == "int"


def test_target_version_must_be_positive():
    module = FakeModule(
        {"filters": None, "prefix_list_ids": None, "target_version": 0},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "target_version must be 1 or greater"


def test_target_version_is_used_for_entries():
    module = FakeModule(
        {
            "filters": None,
            "prefix_list_ids": ["pl-1", "pl-1"],
            "target_version": 2,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[{"PrefixListId": "pl-1", "PrefixListName": "main"}],
        ) as query,
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"Entries": []},
        ) as entries,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert query.call_args.kwargs == {"Filters": [{"Name": "prefix-list-id", "Values": ["pl-1"]}]}
    assert entries.call_args.kwargs["TargetVersion"] == 2


def test_rejects_malformed_prefix_list_response():
    module = FakeModule(
        {"filters": None, "prefix_list_ids": None, "target_version": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail),
    ):
        plugin.main()


def test_rejects_malformed_entry_response():
    module = FakeModule(
        {"filters": None, "prefix_list_ids": None, "target_version": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"PrefixListId": "pl-1"}]),
        patch.object(plugin, "paginated_query_with_retries", return_value={"Entries": [None]}),
        pytest.raises(ModuleFail),
    ):
        plugin.main()


def test_prefix_list_ids_take_precedence_over_the_id_filter():
    module = FakeModule(
        {
            "filters": {"prefix-list-id": "ignored", "prefix-list-name": "main"},
            "prefix_list_ids": ["pl-1"],
            "target_version": None,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert sorted(query.call_args.kwargs["Filters"], key=lambda item: item["Name"]) == [
        {"Name": "prefix-list-id", "Values": ["pl-1"]},
        {"Name": "prefix-list-name", "Values": ["main"]},
    ]
    assert module.params["filters"]["prefix-list-id"] == "ignored"


def test_missing_prefix_list_id_returns_an_empty_list():
    module = FakeModule(
        {"filters": None, "prefix_list_ids": ["pl-missing"], "target_version": None},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        patch.object(plugin, "paginated_query_with_retries") as entries,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["prefix_lists"] == []
    assert "PrefixListIds" not in query.call_args.kwargs
    entries.assert_not_called()


def test_target_version_is_omitted_for_aws_managed_prefix_lists():
    module = FakeModule(
        {"filters": None, "prefix_list_ids": None, "target_version": 1},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "query_list",
            return_value=[
                {"OwnerId": "AWS", "PrefixListId": "pl-02cd2c6b"},
                {"OwnerId": "123456789012", "PrefixListId": "pl-1"},
            ],
        ),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"Entries": [{"Cidr": "10.0.0.0/8"}]},
        ) as entries,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert [entry_call.kwargs for entry_call in entries.call_args_list] == [
        {"PrefixListId": "pl-02cd2c6b"},
        {"PrefixListId": "pl-1", "TargetVersion": 1},
    ]
    assert [prefix_list["entries"] for prefix_list in raised.value.values["prefix_lists"]] == [
        [{"cidr": "10.0.0.0/8"}],
        [{"cidr": "10.0.0.0/8"}],
    ]
