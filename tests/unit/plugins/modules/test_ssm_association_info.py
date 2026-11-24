from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ssm_association_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def run(module, associations):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=associations) as query_list,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods, query_list


def test_module_contract():
    captured = assert_module_contract(plugin)

    assert captured["argument_spec"]["filters"]["type"] == "dict"


def test_scalar_filters_are_converted_to_association_filters():
    result, require_client_methods, query_list = run(FakeModule({"filters": {"Name": "document"}}, client=Mock()), [])

    assert result.values["associations"] == []
    assert require_client_methods.call_args.args[3]["list_associations"] == ("AssociationFilterList",)
    assert query_list.call_args.kwargs["AssociationFilterList"] == [{"key": "Name", "value": "document"}]


def test_single_value_list_filters_are_accepted():
    _result, _require, query_list = run(FakeModule({"filters": {"Name": ["document"]}}, client=Mock()), [])

    assert query_list.call_args.kwargs["AssociationFilterList"] == [{"key": "Name", "value": "document"}]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "filters.AssociationName must not be empty"),
        (None, "filters.AssociationName must not contain a null value"),
        ([None], "filters.AssociationName must not contain a null value"),
    ],
)
def test_empty_or_null_filters_are_rejected_before_any_call(value, message):
    module = FakeModule({"filters": {"Name": "document", "AssociationName": value}}, client=Mock())
    result, require_client_methods, query_list = run(module, [])

    assert result.values["msg"] == message
    require_client_methods.assert_not_called()
    query_list.assert_not_called()


def test_repeated_filter_values_are_left_to_aws():
    module = FakeModule({"filters": {"AssociationName": ["a", "b"]}}, client=Mock())
    _result, _require, query_list = run(module, [])

    assert query_list.call_args.kwargs["AssociationFilterList"] == [
        {"key": "AssociationName", "value": "a"},
        {"key": "AssociationName", "value": "b"},
    ]


def test_associations_include_tags():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": [{"Key": "CostCenter", "Value": "A1"}]}))
    result, _require, _query = run(
        FakeModule({"filters": None}, client=client), [{"AssociationId": "a-1", "Name": "document"}]
    )

    assert result.values["associations"] == [
        {"association_id": "a-1", "name": "document", "tags": {"CostCenter": "A1"}}
    ]


def test_association_deleted_before_its_tags_are_read_is_skipped():
    client = Mock(
        list_tags_for_resource=Mock(
            side_effect=ClientError({"Error": {"Code": "InvalidResourceId"}}, "ListTagsForResource")
        )
    )
    result, _require, _query = run(FakeModule({"filters": None}, client=client), [{"AssociationId": "a-1"}])

    assert result.values["associations"] == []


def test_association_status_names_are_preserved():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": []}))
    association = {
        "AssociationId": "a-1",
        "Overview": {"AssociationStatusAggregatedCount": {"InProgress": 1, "Success": 2}, "Status": "Pending"},
    }
    result, _require, _query = run(FakeModule({"filters": None}, client=client), [association])

    assert result.values["associations"][0]["overview"] == {
        "association_status_aggregated_count": {"InProgress": 1, "Success": 2},
        "status": "Pending",
    }
