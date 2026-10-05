from pathlib import Path
from unittest.mock import Mock, patch

import pytest

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


@pytest.mark.parametrize("overrides", [{"group_ids": ["pg-missing"]}, {"group_names": ["missing"]}])
def test_missing_groups_return_an_empty_list(overrides):
    groups = [] if "group_names" in overrides else GROUPS
    result, _require, _query = run(FakeModule(params(**overrides), client=Mock()), groups)

    assert result.values["placement_groups"] == []


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
