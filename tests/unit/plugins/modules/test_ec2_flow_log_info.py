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
