from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ssm_instance_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
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
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["ping_status"]["choices"] == ["ConnectionLost", "Inactive", "Online"]
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


@pytest.mark.parametrize(
    ("instance_ids", "message"),
    [([f"i-{index}" for index in range(101)], "at most 100"), ([""], "empty entries")],
)
def test_rejects_invalid_instance_ids(instance_ids, message):
    result, _require, _query = run(FakeModule(params(instance_ids=instance_ids)))

    assert message in result.values["msg"]


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


def test_no_matching_instances_returns_empty_lists():
    result, _require, _query = run(FakeModule(params(instance_ids=["i-missing"]), client=Mock()), [])

    assert result.values["instances"] == []
    assert result.values["instance_ids"] == []


@pytest.mark.parametrize(
    ("instances", "message"),
    [
        (
            [{"InstanceId": "i-1"}, None],
            "Unexpected response while describing AWS Systems Manager instances; instance 1 was not a dictionary",
        ),
        (None, "Unexpected response while describing AWS Systems Manager instances; instance list was not a list"),
    ],
)
def test_rejects_malformed_instances(instances, message):
    result, _require, _query = run(FakeModule(params(), client=Mock()), instances)

    assert result.values["msg"] == message


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


def test_warns_when_instance_id_is_invalid():
    module = FakeModule(params(), client=Mock())
    module.warn = Mock()
    result, _require, _query = run(module, [{"InstanceId": "i-1"}, {}])

    assert result.values["instance_ids"] == ["i-1"]
    assert result.values["instances"] == [{"instance_id": "i-1"}, {}]
    module.warn.assert_called_once_with(
        "Unexpected response while describing AWS Systems Manager instances; "
        "instance 1 did not contain a valid InstanceId and was omitted from instance_ids"
    )


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
        FakeModule(params(connection_status=True), client=client), [{"InstanceId": "i-1"}, {}, {"InstanceId": "i-2"}]
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
        {},
        {"instance_id": "i-2", "connection_status": "notconnected"},
    ]


def test_connection_status_error_names_instance():
    client = Mock()
    client.get_connection_status.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "GetConnectionStatus"
    )
    result, _require, _query = run(FakeModule(params(connection_status=True), client=client), [{"InstanceId": "i-1"}])

    assert result.values["msg"] == "Unable to get AWS Systems Manager connection status for i-1"


@pytest.mark.parametrize("response", [None, {}, {"Status": None}, {"Status": 1}])
def test_rejects_malformed_connection_status(response):
    client = Mock()
    client.get_connection_status.return_value = response
    result, _require, _query = run(FakeModule(params(connection_status=True), client=client), [{"InstanceId": "i-1"}])

    assert result.values["msg"] == (
        "Unexpected response while getting AWS Systems Manager connection status for i-1; status was not a string"
    )
