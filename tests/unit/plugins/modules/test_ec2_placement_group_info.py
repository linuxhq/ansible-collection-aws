from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ec2_placement_group_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

GROUPS = [
    {"GroupId": "pg-1", "GroupName": "first", "State": "available", "Strategy": "cluster"},
    {
        "GroupId": "pg-2",
        "GroupName": "second",
        "State": "available",
        "Strategy": "spread",
        "Tags": [{"Key": "Team", "Value": "A"}],
    },
]


def params(**overrides):
    values = {"filters": None, "group_ids": None, "group_names": None}
    values.update(overrides)
    return values


def run(module, groups):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=groups) as query_list,
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
    assert captured["argument_spec"]["group_ids"]["elements"] == "str"
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_group_names_are_sent_as_the_group_name_filter():
    _result, require_client_methods, query_list = run(
        FakeModule(
            params(group_names=["first", "first"], filters={"group-name": "ignored", "strategy": "cluster"}),
            client=Mock(),
        ),
        [],
    )

    assert require_client_methods.call_args.args[3] == {"describe_placement_groups": ("Filters",)}
    assert sorted(query_list.call_args.kwargs["Filters"], key=lambda item: item["Name"]) == [
        {"Name": "group-name", "Values": ["first"]},
        {"Name": "strategy", "Values": ["cluster"]},
    ]
    assert "GroupNames" not in query_list.call_args.kwargs


def test_group_ids_are_matched_locally():
    result, require_client_methods, query_list = run(
        FakeModule(params(group_ids=["pg-2", "pg-2"]), client=Mock()), GROUPS
    )

    assert [group["group_id"] for group in result.values["placement_groups"]] == ["pg-2"]
    assert "GroupIds" not in query_list.call_args.kwargs
    assert require_client_methods.call_args.args[3] == {"describe_placement_groups": ()}


def not_found(code):
    return ClientError({"Error": {"Code": code, "Message": "unknown"}}, "DescribePlacementGroups")


@pytest.mark.parametrize("overrides", [{"group_ids": ["pg-missing"]}, {"group_names": ["missing"]}])
def test_missing_groups_return_an_empty_list(overrides):
    groups = [] if "group_names" in overrides else GROUPS
    client = Mock()
    client.describe_placement_groups.side_effect = not_found("InvalidParameterValue")
    result, _require, _query = run(FakeModule(params(**overrides), client=client), groups)

    assert result.values["placement_groups"] == []


def test_shared_group_ids_are_described_by_id_one_at_a_time():
    shared = {"GroupId": "pg-shared", "GroupName": "shared", "State": "available", "Strategy": "cluster"}
    client = Mock()
    client.describe_placement_groups.side_effect = [
        not_found("InvalidPlacementGroup.Unknown"),
        {"PlacementGroups": [shared]},
        not_found("InvalidParameterValue"),
    ]
    module = FakeModule(
        params(group_ids=["pg-missing", "pg-2", "pg-shared", "bad"], filters={"strategy": "cluster"}), client=client
    )
    result, require_client_methods, _query = run(module, GROUPS)

    assert [group["group_id"] for group in result.values["placement_groups"]] == ["pg-2", "pg-shared"]
    assert [call.kwargs for call in client.describe_placement_groups.call_args_list] == [
        {
            "GroupIds": [group_id],
            "Filters": [{"Name": "strategy", "Values": ["cluster"]}],
            "aws_retry": True,
        }
        for group_id in ["pg-missing", "pg-shared", "bad"]
    ]
    assert require_client_methods.call_args.args[3] == {"describe_placement_groups": ("Filters", "GroupIds")}


def test_shared_group_ids_keep_the_group_name_filter():
    client = Mock()
    client.describe_placement_groups.return_value = {"PlacementGroups": []}
    result, _require, _query = run(
        FakeModule(params(group_ids=["pg-shared"], group_names=["other"]), client=client), []
    )

    assert result.values["placement_groups"] == []
    assert client.describe_placement_groups.call_args.kwargs["Filters"] == [{"Name": "group-name", "Values": ["other"]}]


def test_shared_group_describe_failure_names_the_group():
    client = Mock()
    client.describe_placement_groups.side_effect = not_found("UnauthorizedOperation")
    result, _require, _query = run(FakeModule(params(group_ids=["pg-shared"]), client=client), [])

    assert result.values["msg"] == "Unable to describe EC2 placement group pg-shared"


def test_tags_keep_their_case():
    result, _require, _query = run(FakeModule(params(group_ids=["pg-2"]), client=Mock()), GROUPS)

    assert result.values["placement_groups"][0]["tags"] == {"Team": "A"}


def test_rejects_invalid_placement_group_response():
    result, _require, _query = run(FakeModule(params(), client=Mock()), [None])

    assert "invalid placement group information" in result.values["msg"]


def test_boolean_and_numeric_filter_list_entries_are_sent_as_strings():
    _result, _require, query = run(
        FakeModule(params(filters={"partition-count": [2], "strategy": "cluster", "x-flag": [True]}), client=Mock()),
        [],
    )

    assert query.call_args.kwargs["Filters"] == [
        {"Name": "partition-count", "Values": ["2"]},
        {"Name": "strategy", "Values": ["cluster"]},
        {"Name": "x-flag", "Values": ["true"]},
    ]


def test_group_names_are_batched_with_the_other_filter_values():
    group_names = [f"name-{index}" for index in range(200)]
    module = FakeModule(params(group_names=group_names, filters={"strategy": "cluster"}), client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "query_list",
            side_effect=lambda *args, **kwargs: [
                {"GroupId": f"pg-{len(kwargs['Filters'][1]['Values'])}", "GroupName": "x", "State": "available"}
            ],
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    batches = [{item["Name"]: item["Values"] for item in call.kwargs["Filters"]} for call in query.call_args_list]
    assert [len(batch["group-name"]) for batch in batches] == [199, 1]
    assert all(batch["strategy"] == ["cluster"] for batch in batches)
    assert [value for batch in batches for value in batch["group-name"]] == group_names
    assert require.call_args.args[3] == {"describe_placement_groups": ("Filters",)}
    assert [group["group_id"] for group in raised.value.values["placement_groups"]] == ["pg-199", "pg-1"]


def test_shared_group_id_is_described_with_each_group_name_batch_until_found():
    shared = {"GroupId": "pg-shared", "GroupName": "name-199", "State": "available", "Strategy": "cluster"}
    client = Mock()
    client.describe_placement_groups.side_effect = [{"PlacementGroups": []}, {"PlacementGroups": [shared]}]
    group_names = [f"name-{index}" for index in range(201)]
    result, _require, _query = run(
        FakeModule(params(group_ids=["pg-shared"], group_names=group_names), client=client), []
    )

    assert [group["group_id"] for group in result.values["placement_groups"]] == ["pg-shared"]
    calls = [call.kwargs for call in client.describe_placement_groups.call_args_list]
    assert [call["GroupIds"] for call in calls] == [["pg-shared"], ["pg-shared"]]
    assert [len(call["Filters"][0]["Values"]) for call in calls] == [200, 1]
