from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ssm_instance_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def params(**overrides):
    values = {"connection_status": False, "filters": None, "instance_ids": None, "ping_status": None}
    values.update(overrides)
    return values


def run(module, instances=None):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=instances) as query_list,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods, query_list


def test_module_contract():
    captured = assert_module_contract(plugin)

    assert captured["argument_spec"]["ping_status"]["choices"] == ["ConnectionLost", "Inactive", "Online"]


def test_instance_and_ping_filters_override_and_stringify_filters():
    module = FakeModule(
        params(filters={"PlatformTypes": ["Linux"], "AgentVersion": 3}, instance_ids=["i-1"], ping_status="Online"),
        client=Mock(),
    )
    _result, require_client_methods, query_list = run(module, [])

    assert require_client_methods.call_args.args[3] == {"describe_instance_information": ("Filters",)}
    assert query_list.call_args.kwargs["Filters"] == [
        {"Key": "PlatformTypes", "Values": ["Linux"]},
        {"Key": "AgentVersion", "Values": ["3"]},
        {"Key": "InstanceIds", "Values": ["i-1"]},
        {"Key": "PingStatus", "Values": ["Online"]},
    ]


def test_instance_ids_are_sent_for_aws_to_validate():
    instance_ids = ["", *[f"i-{index}" for index in range(101)]]
    result, _require, query_list = run(FakeModule(params(instance_ids=instance_ids), client=Mock()), [])

    assert isinstance(result, ModuleExit)
    assert query_list.call_args.kwargs["Filters"] == [{"Key": "InstanceIds", "Values": instance_ids}]


def test_null_filter_value_is_rejected_before_describing():
    result, _require, query_list = run(FakeModule(params(filters={"tag:Environment": None}), client=Mock()))

    assert result.values["msg"] == "filters.tag:Environment must not contain a null value"
    query_list.assert_not_called()


def test_instance_ids_replace_a_null_instance_ids_filter():
    module = FakeModule(params(filters={"InstanceIds": None}, instance_ids=["i-1"]), client=Mock())
    _result, _require, query_list = run(module, [])

    assert query_list.call_args.kwargs["Filters"] == [{"Key": "InstanceIds", "Values": ["i-1"]}]


def test_no_matching_instances_returns_empty_lists():
    result, _require, _query = run(FakeModule(params(instance_ids=["i-missing"]), client=Mock()), [])

    assert result.values["instances"] == []
    assert result.values["instance_ids"] == []


def test_returns_ids_and_normalized_instances():
    result, _require, _query = run(FakeModule(params(), client=Mock()), [{"InstanceId": "i-1", "PingStatus": "Online"}])

    assert result.values["instance_ids"] == ["i-1"]
    assert result.values["instances"] == [{"instance_id": "i-1", "ping_status": "Online"}]


def test_association_status_names_are_preserved():
    overview = {"DetailedStatus": "Failed", "InstanceAssociationStatusAggregatedCount": {"Success": 2, "Failed": 1}}
    result, _require, _query = run(
        FakeModule(params(), client=Mock()), [{"InstanceId": "i-1", "AssociationOverview": overview}]
    )

    assert result.values["instances"][0]["association_overview"] == {
        "detailed_status": "Failed",
        "instance_association_status_aggregated_count": {"Success": 2, "Failed": 1},
    }


def test_connection_status_is_not_requested_by_default():
    client = Mock()
    result, require_client_methods, _query = run(FakeModule(params(), client=client), [{"InstanceId": "i-1"}])

    assert require_client_methods.call_args.args[3] == {"describe_instance_information": ()}
    client.get_connection_status.assert_not_called()
    assert result.values["instances"] == [{"instance_id": "i-1"}]


def test_connection_status_is_added_to_each_instance():
    client = Mock()
    client.get_connection_status.side_effect = [{"Status": "connected"}, {"Status": "notconnected"}]
    result, require_client_methods, _query = run(
        FakeModule(params(connection_status=True), client=client), [{"InstanceId": "i-1"}, {"InstanceId": "i-2"}]
    )

    assert require_client_methods.call_args.args[3] == {
        "describe_instance_information": (),
        "get_connection_status": ("Target",),
    }
    assert [call.kwargs for call in client.get_connection_status.call_args_list] == [
        {"Target": "i-1", "aws_retry": True},
        {"Target": "i-2", "aws_retry": True},
    ]
    assert result.values["instances"] == [
        {"instance_id": "i-1", "connection_status": "connected"},
        {"instance_id": "i-2", "connection_status": "notconnected"},
    ]


def test_connection_status_error_names_instance():
    client = Mock()
    client.get_connection_status.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "GetConnectionStatus"
    )
    result, _require, _query = run(FakeModule(params(connection_status=True), client=client), [{"InstanceId": "i-1"}])

    assert result.values["msg"] == "Unable to get AWS Systems Manager connection status for i-1"
