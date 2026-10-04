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


@pytest.mark.parametrize(
    ("response", "context_id", "message"),
    [
        ([], None, "AWS Service Quotas returned an invalid service quota response"),
        ({"Quota": {"ServiceCode": "iam", "QuotaCode": "L-1"}}, None, "mismatched quota"),
        ({"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "wrong"}}}, "expected", "mismatched quota context"),
        ({"Quota": {"Value": 5.0, "QuotaContext": "invalid"}}, None, "invalid quota context"),
    ],
)
def test_quota_from_response_rejects_invalid_response(response, context_id, message):
    with pytest.raises(ModuleFail) as raised:
        plugin.quota_from_response(FakeModule({}), response, "service quota", "ec2", "L-1", context_id)

    assert message in raised.value.values["msg"]


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
