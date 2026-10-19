from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_flow_log_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["resource_ids"]["elements"] == "str"


def test_flow_log_ids_are_sent_to_aws():
    module = FakeModule(
        {
            "filters": None,
            "flow_log_ids": ["fl-1", "fl-1"],
            "resource_ids": None,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_args.args[3] == {"describe_flow_logs": ("FlowLogIds", "MaxResults", "NextToken")}
    assert query.call_args.kwargs["FlowLogIds"] == ["fl-1"]


def test_rejects_invalid_flow_log_response():
    module = FakeModule(
        {
            "filters": None,
            "flow_log_ids": None,
            "resource_ids": None,
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "invalid EC2 flow log" in raised.value.values["msg"]


def test_boolean_and_numeric_filter_list_entries_are_sent_as_strings():
    module = FakeModule(
        {
            "filters": {"max-aggregation-interval": [60], "x-flag": [True]},
            "flow_log_ids": None,
            "resource_ids": ["vpc-1"],
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

    assert query.call_args.kwargs["Filter"] == [
        {"Name": "max-aggregation-interval", "Values": ["60"]},
        {"Name": "x-flag", "Values": ["true"]},
        {"Name": "resource-id", "Values": ["vpc-1"]},
    ]


def test_flow_log_ids_and_resource_ids_are_batched():
    flow_log_ids = [f"fl-{index}" for index in range(101)]
    resource_ids = [f"vpc-{index}" for index in range(201)]
    module = FakeModule(
        {"filters": {"traffic-type": "ALL"}, "flow_log_ids": flow_log_ids, "resource_ids": resource_ids},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin, "query_list", side_effect=lambda *args, **kwargs: [{"FlowLogId": kwargs["FlowLogIds"][0]}]
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert require.call_args.args[3] == {"describe_flow_logs": ("FlowLogIds", "Filter", "MaxResults", "NextToken")}
    requests = [call.kwargs for call in query.call_args_list]
    assert [(len(request["FlowLogIds"]), len(request["Filter"][1]["Values"])) for request in requests] == [
        (100, 200),
        (100, 1),
        (1, 200),
        (1, 1),
    ]
    assert all(request["Filter"][0] == {"Name": "traffic-type", "Values": ["ALL"]} for request in requests)
    assert len(raised.value.values["flow_logs"]) == 4
