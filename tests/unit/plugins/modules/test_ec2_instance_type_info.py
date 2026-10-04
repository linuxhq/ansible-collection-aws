from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_instance_type_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["instance_types"]["elements"] == "str"


def test_instance_type_filter_is_forwarded():
    module = FakeModule(
        {"filters": None, "instance_types": ["t3.micro", "t3.micro"]},
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_args.args[3] == {
        "describe_instance_types": (
            "InstanceTypes",
            "MaxResults",
            "NextToken",
        )
    }
    assert query.call_args.kwargs["InstanceTypes"] == ["t3.micro"]


def test_instance_type_limit_is_rejected():
    assert_module_rejects(
        plugin,
        {
            "filters": None,
            "instance_types": [f"type-{index}" for index in range(101)],
        },
        "instance_types must contain at most 100 unique entries",
    )


def test_rejects_invalid_instance_type_response():
    module = FakeModule({"filters": None, "instance_types": None}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "invalid instance type information" in raised.value.values["msg"]


def run_info(params):
    module = FakeModule(dict({"filters": None, "instance_types": None}, **params), client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    return require.call_args.args[3]["describe_instance_types"], query.call_args.kwargs


def test_list_filter_values_are_sent_as_ec2_strings():
    _methods, request = run_info(
        {
            "filters": {
                "current-generation": True,
                "vcpu-info.default-vcpus": [2, 4],
                "burstable-performance-supported": [False],
                "instance-type": ["t3.*"],
            }
        }
    )

    assert request["Filters"] == [
        {"Name": "current-generation", "Values": ["true"]},
        {"Name": "vcpu-info.default-vcpus", "Values": ["2", "4"]},
        {"Name": "burstable-performance-supported", "Values": ["false"]},
        {"Name": "instance-type", "Values": ["t3.*"]},
    ]


def test_unsupported_region_types_are_requested_only_when_enabled():
    methods, request = run_info({"include_unsupported_in_region": True})
    assert request["IncludeUnsupportedInRegion"] is True
    assert "IncludeUnsupportedInRegion" in methods

    methods, request = run_info({"include_unsupported_in_region": False})
    assert "IncludeUnsupportedInRegion" not in request
    assert "IncludeUnsupportedInRegion" not in methods
