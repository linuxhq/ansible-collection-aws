from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import service_quota_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)


def run(module):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    return raised.value.values


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["quota_code"]["required"] is True
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_missing_adjusted_and_default_quota_returns_empty():
    missing = ClientError({"Error": {"Code": "NoSuchResourceException", "Message": "gone"}}, "GetServiceQuota")
    client = Mock()
    client.get_service_quota.side_effect = missing
    client.get_aws_default_service_quota.side_effect = missing
    result = run(FakeModule({"context_id": None, "quota_code": "L-1", "service_code": "ec2"}, client=client))

    assert result["quota"] == {}


def test_context_id_is_forwarded_to_service_quotas():
    client = Mock(
        get_service_quota=Mock(return_value={"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "arn:context"}}})
    )
    run(FakeModule({"context_id": "arn:context", "quota_code": "L-1", "service_code": "ec2"}, client=client))

    assert client.get_service_quota.call_args.kwargs["ContextId"] == "arn:context"


def test_mismatched_quota_context_fails():
    client = Mock(get_service_quota=Mock(return_value={"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "x"}}}))
    module = FakeModule({"context_id": "arn:context", "quota_code": "L-1", "service_code": "ec2"}, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "AWS Service Quotas returned a mismatched quota context for ec2/L-1"


def test_context_without_applied_value_returns_the_resource_scope_quota():
    missing = ClientError({"Error": {"Code": "NoSuchResourceException", "Message": "gone"}}, "GetServiceQuota")
    fallback = {"Value": 25.0, "QuotaContext": {"ContextScope": "RESOURCE", "ContextId": "*"}}
    client = Mock()
    client.get_service_quota.side_effect = [missing, {"Quota": fallback}]
    result = run(FakeModule({"context_id": "arn:context", "quota_code": "L-1", "service_code": "ec2"}, client=client))

    assert result["quota"] == {"value": 25.0, "quota_context": {"context_scope": "RESOURCE", "context_id": "*"}}
    client.get_aws_default_service_quota.assert_not_called()


def test_missing_resource_level_quota_returns_empty():
    missing = ClientError({"Error": {"Code": "NoSuchResourceException", "Message": "gone"}}, "GetServiceQuota")
    client = Mock()
    client.get_service_quota.side_effect = missing
    client.get_aws_default_service_quota.side_effect = missing
    result = run(FakeModule({"context_id": "arn:context", "quota_code": "L-1", "service_code": "ec2"}, client=client))

    assert result["quota"] == {}
    assert client.get_service_quota.call_count == 2
    client.get_aws_default_service_quota.assert_called_once_with(QuotaCode="L-1", ServiceCode="ec2", aws_retry=True)


def test_metric_dimension_identifiers_are_preserved():
    dimensions = {"Class": "Standard/OnDemand", "class": "distinct", "Resource": "vCPU", "Service": "EC2"}
    current = {
        "QuotaCode": "L-example",
        "ServiceCode": "ec2",
        "Value": 10.0,
        "UsageMetric": {"MetricNamespace": "AWS/Usage", "MetricName": "ResourceCount", "MetricDimensions": dimensions},
    }
    client = Mock(get_service_quota=Mock(return_value={"Quota": current}))
    result = run(FakeModule({"quota_code": "L-example", "service_code": "ec2", "context_id": None}, client=client))

    metric = result["quota"]["usage_metric"]
    assert metric == {"metric_namespace": "AWS/Usage", "metric_name": "ResourceCount", "metric_dimensions": dimensions}
