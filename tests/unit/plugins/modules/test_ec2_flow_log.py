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

ROLE_ARN = "arn:aws:iam::123456789012:role/flow-logs"


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
    base = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    base.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "resource_ids": ["tgw-1"],
            "resource_type": "TransitGateway",
            "state": "present",
            "tags": None,
            "traffic_type": None,
        }
    )
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


def test_tag_keys_may_contain_128_characters_but_not_129():
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "destination_options": None,
            "log_destination_type": None,
            "purge_tags": True,
            "resource_ids": ["vpc-1"],
            "resource_type": "VPC",
            "state": "present",
            "tags": {"k" * 128: "v"},
            "traffic_type": None,
        }
    )
    module = FakeModule(params, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once_with(module.client(), module)

    params["tags"] = {"k" * 129: "v"}
    assert_module_rejects(plugin, params, "tag keys must contain 1 to 128 characters and values at most 256 characters")


def test_partial_create_failure_is_not_reported_as_success():
    client = Mock()
    client.create_flow_logs.return_value = {"Unsuccessful": [{"Error": {"Code": "LimitExceeded"}}]}
    params = dict.fromkeys(plugin.PRESENT_MATCH_FIELDS)
    params.update(
        {
            "deliver_logs_permission_arn": ROLE_ARN,
            "destination_options": None,
            "log_group_name": "flow",
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
            "deliver_logs_permission_arn": ROLE_ARN,
            "destination_options": None,
            "log_group_name": "flow",
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
            "deliver_logs_permission_arn": ROLE_ARN,
            "destination_options": None,
            "log_group_name": "flow",
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
            "deliver_logs_permission_arn": ROLE_ARN,
            "destination_options": None,
            "log_group_name": "flow",
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
            "destination_options": {
                "file_format": "plain-text",
                "hive_compatible_partitions": False,
                "per_hour_partition": False,
            },
            "flow_log_status": "ACTIVE",
            "log_destination": "arn:aws:s3:::new-bucket",
            "log_destination_type": "s3",
            "max_aggregation_interval": 600,
            "resource_id": "vpc-1",
            "tags": {},
            "traffic_type": "ALL",
        }
    ]
    client.create_flow_logs.assert_not_called()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"destination_options": {"file_format": "parquet", "hive_compatible_partitions": None}},
            {
                "destination_options": {
                    "file_format": "parquet",
                    "hive_compatible_partitions": False,
                    "per_hour_partition": False,
                },
                "max_aggregation_interval": 600,
            },
        ),
        ({"max_aggregation_interval": 60}, {"max_aggregation_interval": 60}),
        ({"resource_ids": ["tgw-1"], "resource_type": "TransitGateway"}, {"max_aggregation_interval": 60}),
        ({"tags": {"Name": "logs"}}, {"tags": {"Name": "logs"}}),
    ],
)
def test_check_mode_predicts_the_values_ec2_stores_for_omitted_settings(overrides, expected):
    result = run_present(Mock(), FakeModule(present_params(**overrides), check_mode=True), [])

    flow_log = result["flow_logs"][0]
    assert {key: flow_log.get(key) for key in expected} == expected


def test_check_mode_predicts_no_destination_options_for_cloud_watch_logs():
    params = present_params(
        deliver_logs_permission_arn=ROLE_ARN,
        log_destination=None,
        log_destination_type="cloud-watch-logs",
        log_group_name="logs",
    )
    result = run_present(Mock(), FakeModule(params, check_mode=True), [])

    assert result["flow_logs"] == [
        {
            "deliver_logs_permission_arn": ROLE_ARN,
            "flow_log_status": "ACTIVE",
            "log_destination_type": "cloud-watch-logs",
            "log_group_name": "logs",
            "max_aggregation_interval": 600,
            "resource_id": "vpc-1",
            "tags": {},
            "traffic_type": "ALL",
        }
    ]


@pytest.mark.parametrize(
    ("log_destination_type", "log_destination", "log_group_name"),
    [
        ("cloud-watch-logs", "arn:aws:logs:us-west-2:123456789012:log-group:flow", "flow"),
        ("cloud-watch-logs", "arn:aws:logs:us-west-2:123456789012:log-group:flow:*", "flow"),
        (None, "arn:aws:logs:us-west-2:123456789012:log-group:flow/vpc:*", "flow/vpc"),
        (
            "cloud-watch-logs",
            "arn:aws-us-gov:logs:us-gov-west-1:123456789012:log-group:/aws/vpc/flow-logs:*",
            "/aws/vpc/flow-logs",
        ),
    ],
)
def test_check_mode_predicts_the_log_group_name_of_a_log_group_arn(
    log_destination_type, log_destination, log_group_name
):
    params = present_params(
        deliver_logs_permission_arn=ROLE_ARN,
        log_destination=log_destination,
        log_destination_type=log_destination_type,
    )
    result = run_present(Mock(), FakeModule(params, check_mode=True), [])

    # EC2 returns the destination as sent plus the log group name without the ":*" suffix.
    assert result["flow_logs"] == [
        {
            "deliver_logs_permission_arn": ROLE_ARN,
            "flow_log_status": "ACTIVE",
            "log_destination": log_destination,
            "log_destination_type": "cloud-watch-logs",
            "log_group_name": log_group_name,
            "max_aggregation_interval": 600,
            "resource_id": "vpc-1",
            "tags": {},
            "traffic_type": "ALL",
        }
    ]


@pytest.mark.parametrize(
    ("log_destination_type", "log_destination"),
    [
        ("cloud-watch-logs", "arn:aws:firehose:us-west-2:123456789012:deliverystream:flow"),
        ("cloud-watch-logs", "flow"),
        ("kinesis-data-firehose", "arn:aws:logs:us-west-2:123456789012:log-group:flow"),
    ],
)
def test_check_mode_predicts_no_log_group_name_for_other_destinations(log_destination_type, log_destination):
    params = present_params(log_destination=log_destination, log_destination_type=log_destination_type)
    if log_destination_type == "cloud-watch-logs":
        params["deliver_logs_permission_arn"] = ROLE_ARN

    result = run_present(Mock(), FakeModule(params, check_mode=True), [])

    assert "log_group_name" not in result["flow_logs"][0]


def test_create_sdk_check_covers_every_request_parameter():
    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    client.meta.service_model.operation_model.return_value.input_shape.members = {
        "DestinationOptions": Mock(
            members=dict.fromkeys(("FileFormat", "HiveCompatiblePartitions", "PerHourPartition"))
        )
    }
    params = present_params(
        deliver_cross_account_role="arn:aws:iam::123456789012:role/cross",
        destination_options={"file_format": "parquet", "hive_compatible_partitions": True, "per_hour_partition": None},
        log_format="${version}",
        max_aggregation_interval=60,
        tags={"Name": "logs"},
    )
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, FakeModule(params))

    gated = [call.args[3]["create_flow_logs"] for call in require.call_args_list if "create_flow_logs" in call.args[3]]
    assert client.create_flow_logs.call_count == 1
    assert len(gated) == 1
    assert sorted(gated[0]) == sorted(set(client.create_flow_logs.call_args.kwargs) - {"aws_retry"})
    assert client.create_flow_logs.call_args.kwargs["DestinationOptions"] == {
        "FileFormat": "parquet",
        "HiveCompatiblePartitions": True,
    }


def test_create_fails_before_aws_when_botocore_lacks_a_destination_option():
    client = Mock()
    client.meta.service_model.operation_model.return_value.input_shape.members = {
        "DestinationOptions": Mock(members={"FileFormat": None})
    }
    params = present_params(destination_options={"file_format": "parquet", "per_hour_partition": True})
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert raised.value.values["msg"] == (
        "Installed botocore does not support EC2 create_flow_logs DestinationOptions parameter PerHourPartition"
    )
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


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("resource_ids", "superseded"), [(["vpc-1"], "fl-old"), (["vpc-1", "vpc-2"], "fl-old, fl-old-2")]
)
def test_purge_keeps_old_flow_logs_when_a_matching_flow_log_fails_delivery(resource_ids, superseded, check_mode):
    # The flow log that already matches on vpc-1 is not delivering logs; vpc-2 needs a new flow log.
    matching = dict(
        OLD_FLOW_LOG,
        DeliverLogsErrorMessage="Access error",
        DeliverLogsStatus="FAILED",
        FlowLogId="fl-match",
        FlowLogStatus="ACTIVE",
        LogDestination="arn:aws:s3:::new-bucket",
    )
    flow_logs = [matching, dict(OLD_FLOW_LOG)]
    if "vpc-2" in resource_ids:
        flow_logs.append(dict(OLD_FLOW_LOG, FlowLogId="fl-old-2", ResourceId="vpc-2"))

    client = Mock()
    client.create_flow_logs.return_value = {"FlowLogIds": ["fl-new"]}
    created = {"FlowLogId": "fl-new", "FlowLogStatus": "ACTIVE", "ResourceId": "vpc-2"}
    module = FakeModule(present_params(purge_flow_logs=True, resource_ids=resource_ids), check_mode=check_mode)
    with (
        patch.object(plugin, "get_flow_logs", return_value=flow_logs),
        patch.object(plugin, "query_list", return_value=[created]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    # Check mode fails as the real run does instead of predicting the deletion.
    creates = "vpc-2" in resource_ids and not check_mode
    assert raised.value.values == {
        "changed": creates,
        "msg": f"Replacement EC2 flow logs fl-match are not delivering logs; superseded flow logs {superseded} were kept",
        "replacement_errors": {"fl-match": "Access error"},
    }
    assert client.create_flow_logs.called is creates
    client.delete_flow_logs.assert_not_called()


CREATE_SETTING_MESSAGES = {
    "cloud-watch-logs-role": (
        "deliver_logs_permission_arn is required to create flow logs when log_destination_type is cloud-watch-logs"
    ),
    "cloud-watch-logs-destination": (
        "log_group_name or log_destination is required to create flow logs when log_destination_type is cloud-watch-logs"
    ),
    "kinesis-data-firehose": (
        "log_destination is required to create flow logs when log_destination_type is kinesis-data-firehose"
    ),
    "s3": "log_destination is required to create flow logs when log_destination_type is s3",
}


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"log_destination_type": None, "log_group_name": "flow"}, "cloud-watch-logs-role"),
        (
            {
                "log_destination": "arn:aws:logs:us-west-2:123456789012:log-group:flow",
                "log_destination_type": "cloud-watch-logs",
            },
            "cloud-watch-logs-role",
        ),
        ({"log_destination_type": None}, "cloud-watch-logs-role"),
        ({"deliver_logs_permission_arn": ROLE_ARN, "log_destination_type": None}, "cloud-watch-logs-destination"),
        (
            {"deliver_logs_permission_arn": ROLE_ARN, "log_destination_type": "cloud-watch-logs"},
            "cloud-watch-logs-destination",
        ),
        ({"log_destination_type": "s3"}, "s3"),
        ({"log_destination_type": "s3", "log_group_name": "flow"}, "s3"),
        ({"log_destination_type": "kinesis-data-firehose"}, "kinesis-data-firehose"),
        ({"log_destination_type": "kinesis-data-firehose", "log_group_name": "flow"}, "kinesis-data-firehose"),
    ],
)
def test_create_without_settings_ec2_requires_fails_before_aws(overrides, message, check_mode):
    params = present_params(log_destination=None)
    params.update(overrides)
    client = Mock()
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    # EC2 rejects these CreateFlowLogs requests with InvalidParameter.
    assert raised.value.values == {"msg": CREATE_SETTING_MESSAGES[message]}
    assert client.method_calls == []
    require.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"deliver_cross_account_role": ""}, "deliver_cross_account_role must not be empty"),
        ({"deliver_cross_account_role": " "}, "deliver_cross_account_role must not be empty"),
        (
            {
                "deliver_logs_permission_arn": "",
                "log_destination": None,
                "log_destination_type": None,
                "log_group_name": "flow",
            },
            "deliver_logs_permission_arn must not be empty",
        ),
        (
            {
                "deliver_logs_permission_arn": ROLE_ARN,
                "log_destination": None,
                "log_destination_type": None,
                "log_group_name": " ",
            },
            "log_group_name must not be empty",
        ),
        ({"log_destination": ""}, "log_destination must not be empty"),
        ({"log_format": ""}, "log_format must not be empty"),
        ({"log_format": " "}, "log_format must not be empty"),
    ],
)
def test_blank_present_values_fail_before_aws(overrides, message, check_mode):
    # EC2 rejects these, or accepts a whitespace-only value without storing it, so no flow log ever matches them and
    # check mode would predict a create and the purge of the existing flow log. A rerun after a whitespace-only value
    # was accepted would fail with FlowLogAlreadyExists.
    module = FakeModule(present_params(purge_flow_logs=True, **overrides), check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_flow_logs", return_value=[dict(OLD_FLOW_LOG)]) as get_flow_logs,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": message}
    module.client.assert_not_called()
    get_flow_logs.assert_not_called()


def test_blank_values_still_only_narrow_absent_matches():
    params = present_params(deliver_cross_account_role="", log_format=" ", state="absent")
    module = FakeModule(params, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_absent") as ensure_absent,
    ):
        plugin.main()

    ensure_absent.assert_called_once_with(module.client(), module)


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("overrides", "existing"),
    [
        (
            {"log_destination_type": None, "log_group_name": "flow"},
            {
                "DeliverLogsPermissionArn": ROLE_ARN,
                "FlowLogId": "fl-match",
                "LogDestinationType": "cloud-watch-logs",
                "LogGroupName": "flow",
                "ResourceId": "vpc-1",
                "TrafficType": "ALL",
            },
        ),
        ({"log_destination_type": "s3"}, OLD_FLOW_LOG),
    ],
)
def test_existing_matching_flow_logs_need_no_create_settings(overrides, existing, check_mode):
    params = present_params(log_destination=None)
    params.update(overrides)
    client = Mock()
    result = run_present(client, FakeModule(params, check_mode=check_mode), [dict(existing)])

    assert result["changed"] is False
    assert result["flow_log_ids"] == [existing["FlowLogId"]]
    client.create_flow_logs.assert_not_called()


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


@pytest.mark.parametrize("check_mode", [False, True])
def test_resulting_tag_limit_fails_before_creating_flow_logs(check_mode):
    client = Mock()
    existing_tags = [{"Key": f"aws:reserved{index}", "Value": ""} for index in range(5)]
    existing_tags += [{"Key": f"old{index}", "Value": ""} for index in range(49)]
    existing = dict(OLD_FLOW_LOG, LogDestination="arn:aws:s3:::new-bucket", Tags=existing_tags)
    params = present_params(resource_ids=["vpc-1", "vpc-2"], purge_tags=False, tags={"new0": "", "new1": ""})
    with (
        patch.object(plugin, "get_flow_logs", return_value=[existing]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values["msg"] == "The resulting EC2 flow log tags must contain at most 50 entries"
    assert raised.value.values.get("changed", False) is False
    client.create_flow_logs.assert_not_called()
    client.create_tags.assert_not_called()


@pytest.mark.parametrize(
    ("not_found_ids", "deleted", "changed"),
    [
        (["fl-old", "fl-old-2"], [], False),
        (["fl-old"], ["fl-old-2"], True),
    ],
)
def test_purge_reports_only_flow_logs_actually_deleted(not_found_ids, deleted, changed):
    matching = dict(
        OLD_FLOW_LOG, FlowLogId="fl-match", FlowLogStatus="ACTIVE", LogDestination="arn:aws:s3:::new-bucket"
    )
    client = Mock()
    client.delete_flow_logs.return_value = {
        "Unsuccessful": [
            {"Error": {"Code": "InvalidFlowLogId.NotFound"}, "ResourceId": flow_log_id} for flow_log_id in not_found_ids
        ]
    }
    flow_logs = [matching, dict(OLD_FLOW_LOG), dict(OLD_FLOW_LOG, FlowLogId="fl-old-2")]
    with (
        patch.object(plugin, "get_flow_logs", return_value=flow_logs),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(present_params(purge_flow_logs=True)))

    assert raised.value.values["changed"] is changed
    assert raised.value.values["deleted_flow_log_ids"] == deleted
    client.create_flow_logs.assert_not_called()


def test_describe_batches_resource_id_filter_values():
    resource_ids = [f"vpc-{index}" for index in range(401)]
    with patch.object(
        plugin, "query_list", side_effect=lambda *args, **kwargs: [{"Filter": kwargs["Filter"]}]
    ) as query:
        flow_logs = plugin.get_flow_logs(Mock(), FakeModule({"resource_ids": resource_ids}))

    filter_values = [call.kwargs["Filter"][0]["Values"] for call in query.call_args_list]
    assert [len(values) for values in filter_values] == [200, 200, 1]
    assert [value for values in filter_values for value in values] == resource_ids
    assert len(flow_logs) == 3


@pytest.mark.parametrize(
    ("resource_type", "prefix", "count", "batch_sizes"),
    [
        ("TransitGatewayAttachment", "tgw-attach", 26, [25, 1]),
        ("TransitGateway", "tgw", 26, [25, 1]),
        ("VPC", "vpc", 301, [300, 1]),
    ],
)
def test_create_batches_resource_ids_with_a_token_per_request(resource_type, prefix, count, batch_sizes):
    resource_ids = [f"{prefix}-{index}" for index in range(count)]
    client = Mock()
    client.create_flow_logs.side_effect = lambda **kwargs: {
        "FlowLogIds": [f"fl-{resource_id}" for resource_id in kwargs["ResourceIds"]],
        "Unsuccessful": [],
    }
    module = FakeModule(present_params(resource_ids=resource_ids, resource_type=resource_type, tags={"Name": "logs"}))
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    requests = [call.kwargs for call in client.create_flow_logs.call_args_list]
    assert [len(request["ResourceIds"]) for request in requests] == batch_sizes
    assert [resource_id for request in requests for resource_id in request["ResourceIds"]] == resource_ids
    assert len({request["ClientToken"] for request in requests}) == len(requests)
    assert all(request["TagSpecifications"][0]["Tags"] == [{"Key": "Name", "Value": "logs"}] for request in requests)
    assert raised.value.values["flow_log_ids"] == [f"fl-{resource_id}" for resource_id in resource_ids]


def test_failed_later_create_batch_reports_changed():
    client = Mock()
    client.create_flow_logs.side_effect = [
        {"FlowLogIds": [f"fl-{index}" for index in range(300)], "Unsuccessful": []},
        ClientError({"Error": {"Code": "Throttling", "Message": "no"}}, "CreateFlowLogs"),
    ]
    module = FakeModule(present_params(resource_ids=[f"vpc-{index}" for index in range(301)]))
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True


def test_delete_batches_flow_log_ids():
    flow_log_ids = [f"fl-{index}" for index in range(101)]
    client = Mock()
    client.delete_flow_logs.return_value = {}
    with patch.object(plugin, "require_client_methods"):
        removed = plugin.delete_flow_logs(client, FakeModule({}), flow_log_ids)

    batches = [call.kwargs["FlowLogIds"] for call in client.delete_flow_logs.call_args_list]
    assert [len(batch) for batch in batches] == [100, 1]
    assert removed == flow_log_ids


@pytest.mark.parametrize(
    ("second_response", "unsuccessful"),
    [
        (ClientError({"Error": {"Code": "Throttling", "Message": "no"}}, "DeleteFlowLogs"), None),
        ({"Unsuccessful": [{"Error": {"Code": "Failed"}, "ResourceId": "fl-100"}]}, 1),
    ],
)
def test_failed_later_delete_batch_reports_changed(second_response, unsuccessful):
    client = Mock()
    client.delete_flow_logs.side_effect = [
        {"Unsuccessful": [{"Error": {"Code": "Failed"}, "ResourceId": "fl-0"}]},
        second_response,
    ]
    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.delete_flow_logs(client, FakeModule({}), [f"fl-{index}" for index in range(101)])

    assert raised.value.values["changed"] is True
    assert client.delete_flow_logs.call_count == 2
    if unsuccessful:
        assert [failure["resource_id"] for failure in raised.value.values["unsuccessful"]] == ["fl-0", "fl-100"]


def test_describe_after_create_batches_flow_log_ids():
    resource_ids = [f"vpc-{index}" for index in range(101)]
    client = Mock()
    client.create_flow_logs.side_effect = lambda **kwargs: {
        "FlowLogIds": [f"fl-{resource_id}" for resource_id in kwargs["ResourceIds"]],
        "Unsuccessful": [],
    }
    with (
        patch.object(plugin, "get_flow_logs", return_value=[]),
        patch.object(plugin, "query_list", return_value=[]) as query,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(present_params(resource_ids=resource_ids)))

    batches = [call.kwargs["FlowLogIds"] for call in query.call_args_list]
    assert [len(batch) for batch in batches] == [100, 1]
    assert [flow_log_id for batch in batches for flow_log_id in batch] == [f"fl-{rid}" for rid in resource_ids]
    assert all(call.kwargs["changed"] is True for call in query.call_args_list)
    assert raised.value.values["flow_log_ids"] == [f"fl-{rid}" for rid in resource_ids]


def not_found_error():
    return ClientError(
        {"Error": {"Code": "InvalidFlowLogId.NotFound", "Message": "not found"}},
        "DeleteFlowLogs",
    )


@pytest.mark.parametrize(
    ("remaining", "expected_removed", "delete_calls"),
    [
        ([{"FlowLogId": "fl-live"}], ["fl-live"], 2),
        ([], [], 1),
    ],
)
def test_delete_skips_flow_logs_already_gone_when_ec2_rejects_the_request(remaining, expected_removed, delete_calls):
    client = Mock()
    client.delete_flow_logs.side_effect = [not_found_error(), {}]
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=remaining) as query,
    ):
        removed = plugin.delete_flow_logs(client, FakeModule({}), ["fl-gone", "fl-live"])

    assert removed == expected_removed
    assert query.call_args.kwargs["FlowLogIds"] == ["fl-gone", "fl-live"]
    assert client.delete_flow_logs.call_count == delete_calls
    if delete_calls == 2:
        assert client.delete_flow_logs.call_args.kwargs["FlowLogIds"] == ["fl-live"]


def test_absent_reports_unchanged_when_every_flow_log_is_already_gone():
    client = Mock()
    client.delete_flow_logs.side_effect = not_found_error()
    params = dict.fromkeys(plugin.ABSENT_MATCH_FIELDS)
    params.update({"destination_options": None, "resource_ids": ["vpc-1"]})
    with (
        patch.object(plugin, "get_flow_logs", return_value=[{"FlowLogId": "fl-1", "ResourceId": "vpc-1"}]),
        patch.object(plugin, "query_list", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, FakeModule(params))

    assert raised.value.values["changed"] is False


def test_failed_retry_after_not_found_reports_earlier_deletes_as_changed():
    client = Mock()
    client.delete_flow_logs.side_effect = [
        {},
        not_found_error(),
        ClientError({"Error": {"Code": "Throttling", "Message": "no"}}, "DeleteFlowLogs"),
    ]
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"FlowLogId": "fl-100"}]) as query,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.delete_flow_logs(client, FakeModule({}), [f"fl-{index}" for index in range(102)])

    assert raised.value.values["changed"] is True
    assert query.call_args.kwargs["changed"] is True
    assert client.delete_flow_logs.call_args.kwargs["FlowLogIds"] == ["fl-100"]
