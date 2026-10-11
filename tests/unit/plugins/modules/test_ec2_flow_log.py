from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from botocore.loaders import Loader

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


@pytest.mark.parametrize(
    ("not_found_ids", "changed"),
    [
        (["fl-1", "fl-2"], False),
        (["fl-1"], True),
        ([], True),
    ],
)
def test_absent_reports_changed_only_when_a_flow_log_was_removed(not_found_ids, changed):
    client = Mock()
    client.delete_flow_logs.return_value = {
        "Unsuccessful": [
            {"Error": {"Code": "InvalidFlowLogId.NotFound"}, "ResourceId": flow_log_id} for flow_log_id in not_found_ids
        ]
    }
    params = dict.fromkeys(plugin.ABSENT_MATCH_FIELDS)
    params.update({"destination_options": None, "resource_ids": ["vpc-1"]})
    module = FakeModule(params)
    with (
        patch.object(
            plugin,
            "get_flow_logs",
            return_value=[
                {"FlowLogId": "fl-1", "ResourceId": "vpc-1"},
                {"FlowLogId": "fl-2", "ResourceId": "vpc-1"},
            ],
        ),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is changed
    assert raised.value.values["flow_log_ids"] == ["fl-1", "fl-2"]


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
    assert raised.value.values["changed"] is False


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


def test_check_mode_predicts_only_fields_ec2_returns():
    client = Mock()
    result = run_present(client, FakeModule(present_params(), check_mode=True), [])

    # EC2 flow logs carry no resource type, so the prediction omits it as real runs do.
    assert result["flow_logs"] == [
        {
            "flow_log_status": "ACTIVE",
            "log_destination": "arn:aws:s3:::new-bucket",
            "log_destination_type": "s3",
            "resource_id": "vpc-1",
            "traffic_type": "ALL",
        }
    ]
    client.create_flow_logs.assert_not_called()


def test_create_sends_a_client_token():
    client = Mock()
    run_present(client, FakeModule(present_params()), [])

    token = client.create_flow_logs.call_args.kwargs["ClientToken"]
    assert isinstance(token, str) and 0 < len(token) <= 64


@pytest.mark.parametrize("traffic_type,expected", [(None, "ALL"), ("REJECT", "REJECT")])
def test_regional_nat_gateway_sends_traffic_type_defaulting_to_all(traffic_type, expected):
    client = Mock()
    module = FakeModule(
        present_params(resource_ids=["nat-1"], resource_type="RegionalNatGateway", traffic_type=traffic_type)
    )
    run_present(client, module, [])

    request = client.create_flow_logs.call_args.kwargs
    assert request["ResourceType"] == "RegionalNatGateway"
    assert request["TrafficType"] == expected


def test_regional_nat_gateway_without_traffic_type_does_not_match_a_reject_flow_log():
    flow_log = dict(OLD_FLOW_LOG, LogDestination="arn:aws:s3:::new-bucket", ResourceId="nat-1", TrafficType="REJECT")
    client = Mock()
    module = FakeModule(present_params(resource_ids=["nat-1"], resource_type="RegionalNatGateway"))
    run_present(client, module, [flow_log])

    assert client.create_flow_logs.call_args.kwargs["TrafficType"] == "ALL"


def test_traffic_type_is_handled_for_every_resource_type():
    shapes = Loader().load_service_model("ec2", "service-2")["shapes"]
    resource_types = set(shapes["FlowLogsResourceType"]["enum"])

    assert set(plugin.TRAFFIC_TYPE_RESOURCE_TYPES) | set(plugin.TRANSIT_GATEWAY_RESOURCE_TYPES) == resource_types
    assert not set(plugin.TRAFFIC_TYPE_RESOURCE_TYPES) & set(plugin.TRANSIT_GATEWAY_RESOURCE_TYPES)


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
    assert raised.value.values["changed"] is True
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


def test_partial_create_failure_reports_changed_when_other_flow_logs_were_created():
    client = Mock()
    client.create_flow_logs.return_value = {
        "FlowLogIds": ["fl-1"],
        "Unsuccessful": [{"Error": {"Code": "LimitExceeded"}, "ResourceId": "vpc-2"}],
    }
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(present_params(resource_ids=["vpc-1", "vpc-2"])))

    assert raised.value.values["changed"] is True


def test_describe_after_create_reports_changed_on_failure():
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", side_effect=ModuleFail({"changed": True})) as query,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_present(client, FakeModule(present_params()))

    assert query.call_args.kwargs["changed"] is True
    assert query.call_args.kwargs["FlowLogIds"] == ["fl-new"]


@pytest.mark.parametrize(("missing_resource_ids", "changed"), [([], False), (["vpc-2"], True)])
def test_tag_failure_reports_whether_flow_logs_were_created(missing_resource_ids, changed):
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    client.create_tags.side_effect = ClientError({"Error": {"Code": "Throttling", "Message": "no"}}, "CreateTags")
    existing = dict(OLD_FLOW_LOG, LogDestination="arn:aws:s3:::new-bucket", Tags=[])
    module = FakeModule(present_params(resource_ids=["vpc-1"] + missing_resource_ids, tags={"Name": "logs"}))
    with (
        patch.object(plugin, "get_flow_logs", return_value=[existing]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is changed
    assert client.create_flow_logs.called is changed


def test_later_sdk_operations_are_checked_before_creating_flow_logs():
    client = Mock()
    existing = dict(OLD_FLOW_LOG, LogDestination="arn:aws:s3:::new-bucket", Tags=[])

    def require(_module, _client, _service, methods):
        if "create_tags" in methods:
            raise ModuleFail({"msg": "Installed botocore does not support EC2 create_tags"})

    module = FakeModule(present_params(resource_ids=["vpc-1", "vpc-2"], tags={"Name": "logs"}))
    with (
        patch.object(plugin, "get_flow_logs", return_value=[existing]),
        patch.object(plugin, "require_client_methods", side_effect=require),
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_present(client, module)

    client.create_flow_logs.assert_not_called()


def test_partial_delete_failure_reports_changed_when_other_flow_logs_were_deleted():
    client = Mock()
    client.delete_flow_logs.return_value = {"Unsuccessful": [{"Error": {"Code": "Failed"}, "ResourceId": "fl-2"}]}
    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.delete_flow_logs(client, FakeModule({}), ["fl-1", "fl-2"])

    assert raised.value.values["changed"] is True
