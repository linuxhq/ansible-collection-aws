from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ssm_association_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
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
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["filters"]["type"] == "dict"
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_scalar_filters_are_converted_to_association_filters():
    result, require_client_methods, query_list = run(FakeModule({"filters": {"Name": "document"}}, client=Mock()), [])

    assert result.values["associations"] == []
    assert require_client_methods.call_args.args[3]["list_associations"] == ("AssociationFilterList",)
    assert query_list.call_args.kwargs["AssociationFilterList"] == [{"key": "Name", "value": "document"}]


def test_associations_include_tags():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": [{"Key": "CostCenter", "Value": "A1"}]}))
    result, _require, _query = run(
        FakeModule({"filters": None}, client=client), [{"AssociationId": "a-1", "Name": "document"}]
    )

    assert result.values["associations"] == [
        {"association_id": "a-1", "name": "document", "tags": {"CostCenter": "A1"}}
    ]


def test_rejects_malformed_association():
    result, _require, _query = run(FakeModule({"filters": None}, client=Mock()), [None])

    assert result.values["msg"] == "Unexpected response while listing AWS Systems Manager associations"


def test_rejects_malformed_tags():
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": [None]}))
    result, _require, _query = run(FakeModule({"filters": None}, client=client), [{"AssociationId": "a-1"}])

    assert result.values["msg"] == "Unexpected response while listing tags for association a-1"


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
