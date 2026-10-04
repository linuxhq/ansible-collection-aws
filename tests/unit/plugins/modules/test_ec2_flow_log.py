from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_flow_log as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


def test_sdk_validation_matches_flow_log_requests():
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": {"Name": "main"},
            "traffic_type": None,
        }
    )
    module = Mock(params=params, client=Mock(return_value=Mock()))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    methods = require.call_args.args[3]
    assert methods["describe_flow_logs"] == ("Filter", "MaxResults", "NextToken", "FlowLogIds")

    params.update(state="absent", tags=None)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "ensure_absent"),
    ):
        plugin.main()

    assert require.call_args.args[3] == {"describe_flow_logs": ("Filter", "MaxResults", "NextToken")}


def test_absent_ignores_flow_log_disappearing_during_delete():
    client = Mock()
    client.delete_flow_logs.return_value = {
        "Unsuccessful": [{"Error": {"Code": "InvalidFlowLogId.NotFound"}, "ResourceId": "fl-1"}]
    }
    params = dict.fromkeys(plugin.ABSENT_MATCH_FIELDS)
    params.update({"destination_options": None, "resource_ids": ["vpc-1"]})
    module = FakeModule(params)
    with (
        patch.object(
            plugin,
            "get_flow_logs",
            return_value=[{"FlowLogId": "fl-1", "ResourceId": "vpc-1"}],
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["max_aggregation_interval"]["choices"] == [
        60,
        600,
    ]
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]


def test_resource_ids_are_deduplicated_in_order():
    module = SimpleNamespace(params={"resource_ids": ["vpc-2", "vpc-1", "vpc-2"]})
    assert plugin.normalized_resource_ids(module) == ["vpc-2", "vpc-1"]


def test_empty_destination_options_are_ignored():
    module = SimpleNamespace(params={"destination_options": {"file_format": "parquet", "unused": None}})
    assert plugin.comparable_destination_options(module) == {"file_format": "parquet"}


def test_flow_log_matching_uses_only_managed_destination_options():
    module = SimpleNamespace(params={"resource_ids": ["vpc-1"]})
    flow_logs = [
        {
            "FlowLogId": "fl-match",
            "ResourceId": "vpc-1",
            "LogDestinationType": "s3",
            "DestinationOptions": {
                "FileFormat": "parquet",
                "HiveCompatiblePartitions": True,
            },
        },
        {
            "FlowLogId": "fl-other-resource",
            "ResourceId": "vpc-2",
            "LogDestinationType": "s3",
            "DestinationOptions": {"FileFormat": "parquet"},
        },
    ]

    assert plugin.matching_flow_logs(
        module,
        flow_logs,
        {
            "log_destination_type": "s3",
            "destination_options": {"file_format": "parquet"},
        },
    ) == [flow_logs[0]]


def test_flow_log_matching_rejects_missing_flow_log_id():
    module = FakeModule({"resource_ids": ["vpc-1"]})

    with pytest.raises(ModuleFail) as raised:
        plugin.matching_flow_logs(
            module,
            [{"LogDestinationType": "cloud-watch-logs", "ResourceId": "vpc-1"}],
            {"log_destination_type": "cloud-watch-logs"},
        )

    assert "without a flow log ID" in raised.value.values["msg"]


def test_flow_log_matching_rejects_invalid_flow_log():
    module = FakeModule({"resource_ids": ["vpc-1"]})

    with pytest.raises(ModuleFail) as raised:
        plugin.matching_flow_logs(module, [None], {})

    assert "invalid EC2 flow log" in raised.value.values["msg"]


def test_identical_tag_changes_are_batched_across_flow_logs():
    client = Mock()
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1", "vpc-2"],
            "resource_type": "VPC",
            "state": "present",
            "tags": {"Environment": "prod"},
            "traffic_type": None,
        }
    )
    module = FakeModule(params)
    flow_logs = [
        {
            "FlowLogId": f"fl-{index}",
            "LogDestinationType": "cloud-watch-logs",
            "ResourceId": f"vpc-{index}",
            "Tags": [
                {"Key": "Environment", "Value": "test"},
                {"Key": "Remove", "Value": "yes"},
            ],
            "TrafficType": "ALL",
        }
        for index in (1, 2)
    ]
    with (
        patch.object(plugin, "get_flow_logs", return_value=flow_logs),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    client.delete_tags.assert_called_once_with(
        Resources=["fl-1", "fl-2"],
        Tags=[{"Key": "Remove"}],
        aws_retry=True,
    )
    client.create_tags.assert_called_once_with(
        Resources=["fl-1", "fl-2"],
        Tags=[{"Key": "Environment", "Value": "prod"}],
        aws_retry=True,
    )


def test_invalid_resource_and_destination_combinations_are_rejected():
    base = {
        "destination_options": None,
        "log_destination_type": None,
        "max_aggregation_interval": None,
        "resource_ids": ["tgw-1"],
        "resource_type": "TransitGateway",
        "state": "present",
        "tags": None,
        "traffic_type": None,
    }
    cases = [
        (
            dict(base, resource_ids=[]),
            "resource_ids must contain at least one item",
        ),
        (
            dict(base, traffic_type="ALL"),
            "traffic_type is not supported when resource_type is TransitGateway or TransitGatewayAttachment",
        ),
        (
            dict(base, max_aggregation_interval=600),
            "max_aggregation_interval must be 60 when resource_type is TransitGateway or TransitGatewayAttachment",
        ),
        (
            dict(
                base,
                destination_options={"file_format": "parquet"},
                log_destination_type="cloud-watch-logs",
                resource_type="VPC",
            ),
            "destination_options requires log_destination_type to be s3 when state is present",
        ),
    ]
    for params, message in cases:
        assert_module_rejects(plugin, params, message)


def test_partial_create_failure_is_not_reported_as_success():
    client = Mock()
    client.create_flow_logs.return_value = {"Unsuccessful": [{"Error": {"Code": "LimitExceeded"}}]}
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
    )
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert "one or more resources" in raised.value.values["msg"]
    assert raised.value.values["unsuccessful"][0]["error"]["code"] == "LimitExceeded"


def test_create_rejects_invalid_flow_log_ids():
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": [7], "Unsuccessful": []}
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
    )
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert "valid created EC2 flow log IDs" in raised.value.values["msg"]
    client.describe_flow_logs.assert_not_called()


def test_create_rejects_invalid_described_flow_log():
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-1"], "Unsuccessful": []}
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
    )
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", return_value=[None]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert "invalid created EC2 flow log" in raised.value.values["msg"]


def test_create_result_keeps_ids_missing_from_eventually_consistent_describe():
    client = Mock()
    client.create_flow_logs.return_value = {
        "FlowLogIds": ["fl-created"],
        "Unsuccessful": [],
    }
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
    )
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert raised.value.values["flow_log_ids"] == ["fl-created"]
    assert raised.value.values["flow_logs"] == [{"flow_log_id": "fl-created"}]


def present_params(**overrides):
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": "s3",
            "log_destination": "arn:aws:s3:::new-bucket",
            "purge_flow_logs": False,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
    )
    params.update(overrides)
    return params


OLD_FLOW_LOG = {
    "FlowLogId": "fl-old",
    "LogDestination": "arn:aws:s3:::old-bucket",
    "LogDestinationType": "s3",
    "ResourceId": "vpc-1",
    "TrafficType": "ALL",
}


def run_present(client, module, flow_logs):
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    client.delete_flow_logs.return_value = {}
    with (
        patch.object(plugin, "get_flow_logs", return_value=flow_logs),
        patch.object(plugin, "query_list", return_value=[{"FlowLogId": "fl-new", "ResourceId": "vpc-1"}]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    return result.value.values


def test_changed_settings_keep_the_old_flow_log_by_default():
    client = Mock()
    result = run_present(client, FakeModule(present_params()), [dict(OLD_FLOW_LOG)])

    assert result["changed"] is True
    assert result["deleted_flow_log_ids"] == []
    client.delete_flow_logs.assert_not_called()


def test_purge_replaces_mismatched_flow_logs_after_creating():
    client = Mock()
    manager = Mock()
    manager.attach_mock(client.create_flow_logs, "create")
    manager.attach_mock(client.delete_flow_logs, "delete")
    result = run_present(client, FakeModule(present_params(purge_flow_logs=True)), [dict(OLD_FLOW_LOG)])

    assert result["changed"] is True
    assert result["deleted_flow_log_ids"] == ["fl-old"]
    assert result["flow_log_ids"] == ["fl-new"]
    assert [name for name, _args, _kwargs in manager.mock_calls] == ["create", "delete"]
    client.delete_flow_logs.assert_called_once_with(FlowLogIds=["fl-old"], aws_retry=True)


def test_purge_keeps_matching_flow_logs_and_predicts_in_check_mode():
    matching = dict(OLD_FLOW_LOG, FlowLogId="fl-match", LogDestination="arn:aws:s3:::new-bucket")
    client = Mock()
    module = FakeModule(present_params(purge_flow_logs=True), check_mode=True)
    result = run_present(client, module, [matching, dict(OLD_FLOW_LOG)])

    assert result["changed"] is True
    assert result["deleted_flow_log_ids"] == ["fl-old"]
    assert result["flow_log_ids"] == ["fl-match"]
    client.create_flow_logs.assert_not_called()
    client.delete_flow_logs.assert_not_called()


def test_create_sends_a_client_token():
    client = Mock()
    run_present(client, FakeModule(present_params()), [])

    token = client.create_flow_logs.call_args.kwargs["ClientToken"]
    assert isinstance(token, str) and 0 < len(token) <= 64


@pytest.mark.parametrize("traffic_type", [None, "REJECT"])
def test_regional_nat_gateway_sends_traffic_type_only_when_set(traffic_type):
    client = Mock()
    module = FakeModule(
        present_params(resource_ids=["nat-1"], resource_type="RegionalNatGateway", traffic_type=traffic_type)
    )
    run_present(client, module, [])

    request = client.create_flow_logs.call_args.kwargs
    assert request["ResourceType"] == "RegionalNatGateway"
    assert request.get("TrafficType") == traffic_type


def test_purge_keeps_old_flow_logs_when_a_replacement_fails_delivery():
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    failed = {
        "DeliverLogsErrorMessage": "Access error",
        "DeliverLogsStatus": "FAILED",
        "FlowLogId": "fl-new",
        "FlowLogStatus": "ACTIVE",
        "ResourceId": "vpc-1",
    }
    with (
        patch.object(plugin, "get_flow_logs", return_value=[dict(OLD_FLOW_LOG)]),
        patch.object(plugin, "query_list", return_value=[failed]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(present_params(purge_flow_logs=True)))

    assert "fl-new" in raised.value.values["msg"]
    assert raised.value.values["replacement_errors"] == {"fl-new": "Access error"}
    client.delete_flow_logs.assert_not_called()


def test_purge_waits_for_a_later_run_when_a_replacement_is_not_described_yet():
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    module = FakeModule(present_params(purge_flow_logs=True))
    with (
        patch.object(plugin, "get_flow_logs", return_value=[dict(OLD_FLOW_LOG)]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    assert result.value.values["deleted_flow_log_ids"] == []
    assert "will be purged on a later run" in module.warnings[0]
    client.delete_flow_logs.assert_not_called()
