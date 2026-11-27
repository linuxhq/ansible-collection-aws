from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import service_quota as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
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
    captured = assert_module_contract(plugin)

    assert captured["argument_spec"]["value"]["type"] == "float"
    assert captured["argument_spec"]["context_id"] == {"type": "str"}


@pytest.mark.parametrize("value", [float("inf"), float("nan")])
def test_rejects_non_finite_quota_value(value):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params(value=value))),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "value must be a finite number"


def test_value_above_the_api_maximum_reaches_aws():
    # Service Quotas, not the module, rejects a value outside its accepted range.
    client = Mock()
    client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
    client.request_service_quota_increase.return_value = {"RequestedQuota": {"DesiredValue": 2e10}}
    result, _query, _require = run(FakeModule(params(value=2e10), client=client))

    assert isinstance(result, ModuleExit)
    client.request_service_quota_increase.assert_called_once_with(
        QuotaCode="L-1", ServiceCode="ec2", DesiredValue=2e10, aws_retry=True
    )


@pytest.mark.parametrize("check_mode", [False, True])
def test_empty_context_id_fails_before_any_aws_call(check_mode):
    client = Mock()
    module = FakeModule(params(context_id=""), check_mode=check_mode, client=client)
    module.client = Mock(return_value=client)

    result, query, require_client_methods = run(module)

    assert isinstance(result, ModuleFail)
    assert result.values == {"msg": "context_id must not be empty"}
    module.client.assert_not_called()
    assert client.method_calls == []
    query.assert_not_called()
    require_client_methods.assert_not_called()


def test_validate_current_quota_rejects_a_missing_value():
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_current_quota(FakeModule({}), {"Adjustable": True}, "ec2/L-1")

    assert raised.value.values["msg"] == "AWS service quota ec2/L-1 did not return a valid value"


@pytest.mark.parametrize(
    ("error_reason", "suffix"),
    [
        (
            {"ErrorCode": "DEPENDENCY_ACCESS_DENIED_ERROR", "ErrorMessage": "Access denied for ec2"},
            ": DEPENDENCY_ACCESS_DENIED_ERROR: Access denied for ec2",
        ),
        ({"ErrorCode": "DEPENDENCY_THROTTLING_ERROR"}, ": DEPENDENCY_THROTTLING_ERROR"),
        ({}, ""),
    ],
    ids=["code-and-message", "code-only", "empty"],
)
def test_validate_current_quota_names_the_error_reason(error_reason, suffix):
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_current_quota(FakeModule({}), {"ErrorReason": error_reason}, "ec2/L-1")

    assert raised.value.values["msg"] == f"AWS service quota ec2/L-1 did not return a valid value{suffix}"


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
    # The paginator sends no MaxResults, so the history listing is not gated on it.
    assert methods["list_requested_service_quota_change_history_by_quota"] == (
        "NextToken",
        "Status",
        "QuotaCode",
        "ServiceCode",
        "QuotaRequestedAtLevel",
    )
    assert methods["get_aws_default_service_quota"] == ("QuotaCode", "ServiceCode")


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
    assert result.values["msg"] == "AWS Service Quotas returned a mismatched quota context for ec2/L-1 for arn:resource"
    client.request_service_quota_increase.assert_not_called()


def test_missing_applied_and_default_quota_fails():
    client = Mock()
    client.get_service_quota.side_effect = missing("GetServiceQuota")
    client.get_aws_default_service_quota.side_effect = missing("GetAWSDefaultServiceQuota")
    result = run(FakeModule(params(), client=client))[0]

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "AWS service quota ec2/L-1 does not exist"


RESOURCE_SCOPE_QUOTA = {
    "QuotaCode": "L-1",
    "ServiceCode": "ec2",
    "Value": 5.0,
    "QuotaContext": {"ContextScope": "RESOURCE", "ContextId": "*"},
}


def test_context_without_applied_value_requests_a_resource_level_increase():
    client = Mock()
    client.get_service_quota.side_effect = [missing("GetServiceQuota"), {"Quota": RESOURCE_SCOPE_QUOTA}]
    client.request_service_quota_increase.return_value = {
        "RequestedQuota": {"DesiredValue": 10.0, "QuotaContext": {"ContextId": "arn:resource"}}
    }
    result, query, _require = run(FakeModule(params(context_id="arn:resource"), client=client))

    assert result.values["changed"]
    assert result.values["current_quota"]["value"] == 5.0
    assert result.values["current_quota"]["quota_context"]["context_id"] == "*"
    assert all(call.kwargs["QuotaRequestedAtLevel"] == "RESOURCE" for call in query.call_args_list)
    client.request_service_quota_increase.assert_called_once_with(
        QuotaCode="L-1", ServiceCode="ec2", ContextId="arn:resource", DesiredValue=10.0, aws_retry=True
    )


def test_context_without_applied_value_check_mode_reports_the_context():
    client = Mock()
    client.get_service_quota.side_effect = [missing("GetServiceQuota"), missing("GetServiceQuota")]
    client.get_aws_default_service_quota.return_value = {"Quota": {"Value": 5.0}}
    result = run(FakeModule(params(context_id="arn:resource"), check_mode=True, client=client))[0]

    assert result.values["changed"]
    assert result.values["requested_quota"]["quota_context"] == {"context_id": "arn:resource"}
    assert result.values["requested_quota"]["quota_requested_at_level"] == "RESOURCE"
    client.request_service_quota_increase.assert_not_called()


def test_context_without_applied_value_at_the_desired_value_is_unchanged():
    client = Mock()
    client.get_service_quota.side_effect = [
        missing("GetServiceQuota"),
        {"Quota": dict(RESOURCE_SCOPE_QUOTA, Value=10.0)},
    ]
    result = run(FakeModule(params(context_id="arn:resource"), client=client))[0]

    assert isinstance(result, ModuleExit)
    assert not result.values["changed"]
    client.request_service_quota_increase.assert_not_called()


def test_missing_resource_level_quota_fails():
    client = Mock()
    client.get_service_quota.side_effect = missing("GetServiceQuota")
    client.get_aws_default_service_quota.side_effect = missing("GetAWSDefaultServiceQuota")
    result = run(FakeModule(params(context_id="arn:resource"), client=client))[0]

    assert isinstance(result, ModuleFail)
    assert result.values["msg"] == "AWS service quota ec2/L-1 for arn:resource does not exist"
    client.request_service_quota_increase.assert_not_called()
