# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.service_quotas import (
    get_quota,
    quota_from_response,
    quota_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail


def error(code, operation):
    return ClientError({"Error": {"Code": code, "Message": "error"}}, operation)


@pytest.mark.parametrize(
    ("response", "context_id", "message"),
    [
        ([], None, "AWS Service Quotas returned an invalid service quota response"),
        ({"Quota": {}}, None, "AWS Service Quotas returned an invalid service quota response"),
        ({"Quota": {"ServiceCode": "iam", "QuotaCode": "L-1"}}, None, "mismatched quota for ec2/L-1"),
        ({"Quota": {"Value": 5.0, "QuotaContext": "invalid"}}, None, "invalid quota context"),
        ({"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "wrong"}}}, "expected", "mismatched quota context"),
        ({"Quota": {"Value": 5.0}}, "expected", "mismatched quota context"),
    ],
)
def test_quota_from_response_rejects_invalid_response(response, context_id, message):
    with pytest.raises(ModuleFail) as raised:
        quota_from_response(FakeModule({}), response, "service quota", "ec2", "L-1", context_id)

    assert message in raised.value.values["msg"]


@pytest.mark.parametrize("scope", ["ACCOUNT", "UNKNOWN"])
def test_quota_from_response_rejects_a_non_resource_scope(scope):
    response = {"Quota": {"Value": 5.0, "QuotaContext": {"ContextScope": scope}}}
    with pytest.raises(ModuleFail) as raised:
        quota_from_response(FakeModule({}), response, "service quota", "ec2", "L-1", resource_scope=True)

    assert "mismatched quota context" in raised.value.values["msg"]


@pytest.mark.parametrize("quota", [{"Value": 5.0}, {"Value": 5.0, "QuotaContext": {"ContextScope": "RESOURCE"}}])
def test_quota_from_response_accepts_a_resource_scope(quota):
    response = {"Quota": quota}

    assert quota_from_response(FakeModule({}), response, "service quota", "ec2", "L-1", resource_scope=True) == quota


def test_quota_from_response_accepts_matching_context():
    quota = {"Value": 5.0, "QuotaContext": {"ContextId": "arn:context"}}

    assert quota_from_response(FakeModule({}), {"Quota": quota}, "service quota", "ec2", "L-1", "arn:context") == quota


def test_get_quota_returns_the_applied_quota():
    client = Mock(get_service_quota=Mock(return_value={"Quota": {"Value": 5.0}}))

    assert get_quota(client, FakeModule({}), "ec2", "L-1") == {"Value": 5.0}
    client.get_service_quota.assert_called_once_with(QuotaCode="L-1", ServiceCode="ec2", aws_retry=True)
    client.get_aws_default_service_quota.assert_not_called()


def test_get_quota_falls_back_to_the_default_quota():
    client = Mock()
    client.get_service_quota.side_effect = error("NoSuchResourceException", "GetServiceQuota")
    client.get_aws_default_service_quota.return_value = {"Quota": {"Value": 10.0}}

    assert get_quota(client, FakeModule({}), "ec2", "L-1") == {"Value": 10.0}
    client.get_aws_default_service_quota.assert_called_once_with(QuotaCode="L-1", ServiceCode="ec2", aws_retry=True)


def test_get_quota_returns_none_when_the_default_quota_is_missing():
    client = Mock()
    client.get_service_quota.side_effect = error("NoSuchResourceException", "GetServiceQuota")
    client.get_aws_default_service_quota.side_effect = error("NoSuchResourceException", "GetAWSDefaultServiceQuota")

    assert get_quota(client, FakeModule({}), "ec2", "L-1") is None


RESOURCE_SCOPE_QUOTA = {
    "QuotaCode": "L-1",
    "ServiceCode": "ec2",
    "Value": 25.0,
    "QuotaContext": {"ContextScope": "RESOURCE", "ContextScopeType": "AWS::IAM::Role", "ContextId": "*"},
}


def test_get_quota_falls_back_to_the_resource_scope_quota_for_a_context():
    client = Mock()
    client.get_service_quota.side_effect = [
        error("NoSuchResourceException", "GetServiceQuota"),
        {"Quota": RESOURCE_SCOPE_QUOTA},
    ]

    assert get_quota(client, FakeModule({}), "ec2", "L-1", "arn:context") == RESOURCE_SCOPE_QUOTA
    assert [call.kwargs for call in client.get_service_quota.call_args_list] == [
        {"QuotaCode": "L-1", "ServiceCode": "ec2", "ContextId": "arn:context", "aws_retry": True},
        {"QuotaCode": "L-1", "ServiceCode": "ec2", "aws_retry": True},
    ]
    client.get_aws_default_service_quota.assert_not_called()


def test_get_quota_falls_back_to_the_default_quota_for_a_context():
    default = {"Value": 20.0, "QuotaContext": {"ContextScope": "RESOURCE", "ContextScopeType": "AWS::IAM::Role"}}
    client = Mock()
    client.get_service_quota.side_effect = error("NoSuchResourceException", "GetServiceQuota")
    client.get_aws_default_service_quota.return_value = {"Quota": default}

    assert get_quota(client, FakeModule({}), "ec2", "L-1", "arn:context") == default
    assert client.get_service_quota.call_count == 2
    client.get_aws_default_service_quota.assert_called_once_with(QuotaCode="L-1", ServiceCode="ec2", aws_retry=True)


def test_get_quota_returns_none_when_a_context_quota_is_missing():
    client = Mock()
    client.get_service_quota.side_effect = error("NoSuchResourceException", "GetServiceQuota")
    client.get_aws_default_service_quota.side_effect = error("NoSuchResourceException", "GetAWSDefaultServiceQuota")

    assert get_quota(client, FakeModule({}), "ec2", "L-1", "arn:context") is None


@pytest.mark.parametrize(
    ("fallback", "message"),
    [
        ({"Value": 5.0, "QuotaContext": {"ContextScope": "ACCOUNT"}}, "mismatched quota context"),
        ({"Value": 5.0, "QuotaCode": "L-2"}, "mismatched quota"),
    ],
)
def test_get_quota_rejects_an_invalid_context_fallback(fallback, message):
    client = Mock()
    client.get_service_quota.side_effect = [error("NoSuchResourceException", "GetServiceQuota"), {"Quota": fallback}]

    with pytest.raises(ModuleFail) as raised:
        get_quota(client, FakeModule({}), "ec2", "L-1", "arn:context")

    assert message in raised.value.values["msg"]


def test_get_quota_reports_context_fallback_failures():
    client = Mock()
    client.get_service_quota.side_effect = [
        error("NoSuchResourceException", "GetServiceQuota"),
        error("AccessDeniedException", "GetServiceQuota"),
    ]

    with pytest.raises(ModuleFail) as raised:
        get_quota(client, FakeModule({}), "ec2", "L-1", "arn:context")

    assert raised.value.values["msg"] == "Unable to get AWS service quota ec2/L-1 for arn:context"


@pytest.mark.parametrize(
    ("applied_error", "default_error", "message"),
    [
        (error("AccessDeniedException", "GetServiceQuota"), None, "Unable to get AWS service quota ec2/L-1"),
        (
            error("NoSuchResourceException", "GetServiceQuota"),
            error("AccessDeniedException", "GetAWSDefaultServiceQuota"),
            "Unable to get AWS default service quota ec2/L-1",
        ),
    ],
)
def test_get_quota_reports_lookup_failures(applied_error, default_error, message):
    client = Mock()
    client.get_service_quota.side_effect = applied_error
    client.get_aws_default_service_quota.side_effect = default_error

    with pytest.raises(ModuleFail) as raised:
        get_quota(client, FakeModule({}), "ec2", "L-1")

    assert raised.value.values["msg"] == message


def test_quota_to_ansible_dict_preserves_metric_dimensions():
    dimensions = {"Class": "Standard/OnDemand", "class": "distinct"}
    quota = {"QuotaCode": "L-1", "UsageMetric": {"MetricName": "ResourceCount", "MetricDimensions": dimensions}}

    assert quota_to_ansible_dict(quota) == {
        "quota_code": "L-1",
        "usage_metric": {"metric_name": "ResourceCount", "metric_dimensions": dimensions},
    }
