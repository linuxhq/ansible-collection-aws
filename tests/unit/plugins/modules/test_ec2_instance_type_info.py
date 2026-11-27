from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_instance_type_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["instance_types"]["elements"] == "str"


def run_info(params):
    module = FakeModule(
        dict({"filters": None, "include_unsupported_in_region": False, "instance_types": None}, **params), client=Mock()
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    return require.call_args.args[3]["describe_instance_types"], query.call_args.kwargs


def test_instance_type_filter_is_forwarded():
    methods, request = run_info({"instance_types": ["t3.micro", "t3.micro"]})

    assert methods == (
        "Filters",
        "MaxResults",
        "NextToken",
    )
    # InstanceTypes fails for types not offered in the region; the filter returns no entry.
    assert "InstanceTypes" not in request
    assert request["Filters"] == [{"Name": "instance-type", "Values": ["t3.micro"]}]


def test_instance_types_take_precedence_over_the_instance_type_filter():
    _methods, request = run_info(
        {
            "filters": {"current-generation": True, "instance-type": ["m5.*"]},
            "instance_types": ["hpc7g.16xlarge"],
        }
    )

    assert request["Filters"] == [
        {"Name": "current-generation", "Values": ["true"]},
        {"Name": "instance-type", "Values": ["hpc7g.16xlarge"]},
    ]


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


def test_scalar_filter_values_are_sent_as_ec2_strings():
    _methods, request = run_info(
        {
            "filters": {
                "memory-info.size-in-mib": 1024,
                "network-info.baseline-bandwidth-in-gbps": 0.5,
                "burstable-performance-supported": False,
                "instance-type": "t3.*",
            }
        }
    )

    assert request["Filters"] == [
        {"Name": "memory-info.size-in-mib", "Values": ["1024"]},
        {"Name": "network-info.baseline-bandwidth-in-gbps", "Values": ["0.5"]},
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
