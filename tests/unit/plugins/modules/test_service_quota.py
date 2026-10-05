from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import service_quota as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)


def params(**overrides):
    values = {"context_id": None, "quota_code": "L-1", "service_code": "ec2", "value": 10.0}
    values.update(overrides)
    return values


def missing(operation):
    return ClientError({"Error": {"Code": "NoSuchResourceException", "Message": "gone"}}, operation)


def run(module, history=None):
    """Run main() with the history query patched, returning the module result and the query calls."""
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=history or [{"RequestedQuotas": []}, {"RequestedQuotas": []}],
        ) as query,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, query, require_client_methods


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["value"]["type"] == "float"
    assert captured["argument_spec"]["context_id"] == {"type": "str"}
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_rejects_invalid_quota_value(value):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params(value=value))),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "between 0" in raised.value.values["msg"]


def test_response_resource_rejects_invalid_response():
    with pytest.raises(ModuleFail) as raised:
        plugin.response_resource(FakeModule({}), [], "Quota", "service quota")

    assert raised.value.values["msg"] == "AWS Service Quotas returned an invalid service quota response"


def test_response_resources_rejects_invalid_entry():
    with pytest.raises(ModuleFail) as raised:
        plugin.response_resources(FakeModule({}), {"RequestedQuotas": [None]}, "RequestedQuotas", "quota history")

    assert raised.value.values["msg"] == "AWS Service Quotas returned an invalid quota history entry"


@pytest.mark.parametrize("quota", [{"Value": "5"}, {"Value": True}, {"Value": float("nan")}, {"Adjustable": True}])
def test_validate_current_quota_rejects_invalid_value(quota):
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_current_quota(FakeModule({}), quota, "ec2", "L-1")

    assert raised.value.values["msg"] == "AWS service quota ec2/L-1 did not return a valid value"


def test_validate_current_quota_accepts_large_integer_without_crashing():
    plugin.validate_current_quota(FakeModule({}), {"Value": 10**400}, "ec2", "L-1")


@pytest.mark.parametrize(
    ("request_", "status", "message"),
    [({}, None, "invalid request"), ({"Status": "PENDING"}, "CASE_OPENED", "mismatched request")],
)
def test_validate_quota_request_rejects_invalid_request(request_, status, message):
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_quota_request(FakeModule({}), request_, "ec2", "L-1", status=status)

    assert message in raised.value.values["msg"]


def test_check_mode_reports_the_quota_request():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
    result, _query, require_client_methods = run(FakeModule(params(), check_mode=True, client=client))

    assert result.values["changed"]
    assert result.values["requested_quota"]["desired_value"] == 10.0
    assert result.values["requested_quota"]["quota_requested_at_level"] == "ACCOUNT"
    client.request_service_quota_increase.assert_not_called()
    assert "request_service_quota_increase" not in require_client_methods.call_args.args[3]


def test_pending_request_prevents_a_duplicate_request():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
    module = FakeModule(params(), client=client)
    module.warn = Mock()
    result = run(module, [{"RequestedQuotas": [{"Status": "CASE_OPENED", "DesiredValue": 10.0}]}, {}])[0]

    assert not result.values["changed"]
    client.request_service_quota_increase.assert_not_called()
    module.warn.assert_not_called()


def test_smaller_pending_request_is_reported():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
    module = FakeModule(params(value=20.0), client=client)
    module.warn = Mock()
    result = run(module, [{"RequestedQuotas": []}, {"RequestedQuotas": [{"Status": "PENDING", "DesiredValue": 15.0}]}])[
        0
    ]

    assert not result.values["changed"]
    module.warn.assert_called_once_with(
        "AWS service quota ec2/L-1 has an open request for 15.0, "
        "so an increase to 20.0 can be requested only after it is resolved"
    )


@pytest.mark.parametrize("check_mode", [False, True])
def test_non_adjustable_quota_fails_before_requesting(check_mode):
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0, "Adjustable": False}}
    result = run(FakeModule(params(), check_mode=check_mode, client=client))[0]

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "AWS service quota ec2/L-1 is not adjustable, so it cannot be increased to 10.0"
    client.request_service_quota_increase.assert_not_called()


def test_non_adjustable_quota_at_the_desired_value_is_unchanged():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 10.0, "Adjustable": False}}
    result = run(FakeModule(params(), client=client))[0]

    assert isinstance(result, ModuleExit)
    assert not result.values["changed"]


def test_missing_applied_quota_falls_back_to_default():
    client = Mock()
    client.get_service_quota.side_effect = missing("GetServiceQuota")
    client.get_aws_default_service_quota.return_value = {"Quota": {"Value": 10.0}}
    result = run(FakeModule(params(), client=client))[0]

    assert not result.values["changed"]
    client.get_aws_default_service_quota.assert_called_once_with(QuotaCode="L-1", ServiceCode="ec2", aws_retry=True)


def test_context_id_requests_a_resource_level_increase():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "arn:resource"}}}
    client.request_service_quota_increase.return_value = {
        "RequestedQuota": {"DesiredValue": 10.0, "QuotaContext": {"ContextId": "arn:resource"}}
    }
    other = {"Status": "PENDING", "DesiredValue": 10.0, "QuotaContext": {"ContextId": "arn:other"}}
    result, query, require_client_methods = run(
        FakeModule(params(context_id="arn:resource"), client=client),
        [{"RequestedQuotas": []}, {"RequestedQuotas": [other]}],
    )

    # A pending request for another resource does not block this one.
    assert result.values["changed"]
    assert result.values["pending_requests"] == []
    client.get_service_quota.assert_called_once_with(
        QuotaCode="L-1", ServiceCode="ec2", ContextId="arn:resource", aws_retry=True
    )
    assert all(call.kwargs["QuotaRequestedAtLevel"] == "RESOURCE" for call in query.call_args_list)
    client.request_service_quota_increase.assert_called_once_with(
        QuotaCode="L-1", ServiceCode="ec2", ContextId="arn:resource", DesiredValue=10.0, aws_retry=True
    )
    methods = require_client_methods.call_args.args[3]
    assert "ContextId" in methods["get_service_quota"]
    assert "ContextId" in methods["request_service_quota_increase"]
    assert "QuotaRequestedAtLevel" in methods["list_requested_service_quota_change_history_by_quota"]
    assert "get_aws_default_service_quota" not in methods


def test_context_id_check_mode_reports_the_context():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "arn:resource"}}}
    result = run(FakeModule(params(context_id="arn:resource"), check_mode=True, client=client))[0]

    assert result.values["requested_quota"]["quota_context"] == {"context_id": "arn:resource"}
    assert result.values["requested_quota"]["quota_requested_at_level"] == "RESOURCE"


def test_mismatched_quota_context_fails_before_requesting():
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "arn:other"}}}
    result = run(FakeModule(params(context_id="arn:resource"), client=client))[0]

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "AWS Service Quotas returned a mismatched quota context for ec2/L-1"
    client.request_service_quota_increase.assert_not_called()


def test_missing_applied_and_default_quota_fails():
    client = Mock()
    client.get_service_quota.side_effect = missing("GetServiceQuota")
    client.get_aws_default_service_quota.side_effect = missing("GetAWSDefaultServiceQuota")
    result = run(FakeModule(params(), client=client))[0]

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "AWS service quota ec2/L-1 does not exist"


def test_missing_resource_level_quota_fails_without_default_fallback():
    client = Mock()
    client.get_service_quota.side_effect = missing("GetServiceQuota")
    result = run(FakeModule(params(context_id="arn:resource"), client=client))[0]

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "AWS service quota ec2/L-1 for arn:resource does not exist"
    client.get_aws_default_service_quota.assert_not_called()


def test_metric_dimension_identifiers_are_preserved():
    dimensions = {"Class": "Standard/OnDemand", "class": "distinct", "Resource": "vCPU", "Service": "EC2"}
    current = {
        "QuotaCode": "L-example",
        "ServiceCode": "ec2",
        "Value": 10.0,
        "UsageMetric": {"MetricNamespace": "AWS/Usage", "MetricName": "ResourceCount", "MetricDimensions": dimensions},
    }
    client = Mock(get_service_quota=Mock(return_value={"Quota": current}))
    result = run(FakeModule(params(quota_code="L-example"), client=client))[0]

    metric = result.values["current_quota"]["usage_metric"]
    assert metric == {"metric_namespace": "AWS/Usage", "metric_name": "ResourceCount", "metric_dimensions": dimensions}


@pytest.mark.parametrize(
    "response",
    [{}, {"RequestedQuota": {"DesiredValue": 20.0}}],
)
def test_invalid_request_response_reports_changed(response):
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
    client.request_service_quota_increase.return_value = response
    result, _query, _require = run(FakeModule(params(), client=client))

    assert isinstance(result, ModuleFail)
    assert result.values["changed"] is True


def test_invalid_listed_request_reports_unchanged():
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_quota_request(FakeModule({}), {}, "ec2", "L-1", status="PENDING")

    assert raised.value.values["changed"] is False
