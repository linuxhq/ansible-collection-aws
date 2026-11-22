from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import wafv2_web_acl_logging as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

ARN = "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/main/acl-1"


def params(**overrides):
    values = {"log_destination_configs": ["arn:log"], "resource_arn": ARN, "state": "present"}
    values.update(overrides)
    return values


def nonexistent(operation):
    return ClientError({"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}}, operation)


def run_main(module):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "ensure_present", side_effect=lambda client, module: module.exit_json(present=True)),
        patch.object(plugin, "ensure_absent", side_effect=lambda client, module: module.exit_json()),
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods


def run_present(client, module, current):
    with (
        patch.object(plugin, "get_logging_configuration", return_value=current),
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.ensure_present(client, module)

    return raised.value


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["required_if"] == [("state", "present", ["log_destination_configs"])]
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


@pytest.mark.parametrize(
    ("resource_arn", "region"),
    [
        (ARN, "us-east-1"),
        ("arn:aws:wafv2:us-east-1:123456789012:global/webacl/edge/acl-2", "us-east-1"),
        # AWS WAFv2 rejects a web ACL ARN from another region with WAFInvalidParameterException.
        ("arn:aws:wafv2:us-west-2:123456789012:regional/webacl/main/acl-1", "us-east-1"),
        ("arn:aws:wafv2:us-east-1:123456789012:global/webacl/edge/acl-2", "us-west-2"),
    ],
)
def test_web_acl_arns_reach_aws(resource_arn, region):
    result, require_client_methods = run_main(
        FakeModule(params(resource_arn=resource_arn), client=Mock(), region=region)
    )

    assert result.values == {"present": True}
    assert "get_web_acl" not in require_client_methods.call_args.args[3]


@pytest.mark.parametrize(
    ("resource_arn", "message"),
    [
        ("arn:web-acl", "resource_arn must be an AWS WAFv2 web ACL ARN, not arn:web-acl"),
        ("", "resource_arn must be an AWS WAFv2 web ACL ARN, not "),
        (
            "arn:aws:wafv2:us-east-1:123456789012:regional/ipset/main/set-1",
            "resource_arn must be an AWS WAFv2 web ACL ARN, not arn:aws:wafv2:us-east-1:123456789012:regional/ipset/main/set-1",
        ),
    ],
)
def test_non_web_acl_arn_fails_before_aws(resource_arn, message):
    # AWS WAFv2 answers a non-web-ACL ARN with a retryable InternalFailure rather than a validation error.
    result, require_client_methods = run_main(FakeModule(params(resource_arn=resource_arn), client=Mock()))

    assert result.values["msg"] == message
    require_client_methods.assert_not_called()


# AWS WAFv2, not the module, rejects a destination list it does not accept.
@pytest.mark.parametrize("destinations", [["arn:first", "arn:second"], [""]])
def test_destination_lists_reach_aws(destinations):
    result, require_client_methods = run_main(FakeModule(params(log_destination_configs=destinations)))

    assert result.values == {"present": True}
    require_client_methods.assert_called_once()


def test_check_mode_returns_desired_logging_configuration():
    client = Mock()
    result = run_present(client, FakeModule(params(), check_mode=True), None)

    assert result.values["changed"]
    assert result.values["logging_configuration"] == {
        "log_destination_configs": ["arn:log"],
        "log_scope": "CUSTOMER",
        "log_type": "WAF_LOGS",
        "managed_by_firewall_manager": False,
        "resource_arn": ARN,
    }
    client.get_web_acl.assert_not_called()
    client.put_logging_configuration.assert_not_called()


@pytest.mark.parametrize(
    "current",
    [
        None,
        {
            "LogDestinationConfigs": ["arn:old"],
            "LogScope": "CUSTOMER",
            "LogType": "WAF_LOGS",
            "LoggingFilter": {"DefaultBehavior": "KEEP", "Filters": []},
            "ManagedByFirewallManager": False,
            "ResourceArn": ARN,
        },
    ],
)
def test_check_mode_predicts_the_stored_configuration_a_put_returns(current):
    stored = dict(
        current or {"LogScope": "CUSTOMER", "LogType": "WAF_LOGS", "ManagedByFirewallManager": False},
        LogDestinationConfigs=["arn:new"],
        ResourceArn=ARN,
    )
    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.put_logging_configuration.return_value = {"LoggingConfiguration": stored}
        results[check_mode] = run_present(
            client, FakeModule(params(log_destination_configs=["arn:new"]), check_mode=check_mode), current
        ).values

    assert results[True] == results[False]


def test_missing_web_acl_error_from_the_put_passes_through():
    # A missing web ACL also has no logging configuration, so PutLoggingConfiguration, the only write, reports it.
    client = Mock()
    client.put_logging_configuration.side_effect = nonexistent("PutLoggingConfiguration")
    result = run_present(client, FakeModule(params()), None)

    assert result.values["msg"] == f"Unable to manage AWS WAFv2 logging configuration for {ARN}"
    client.get_web_acl.assert_not_called()


def test_existing_logging_configuration_is_unchanged():
    client = Mock()
    current = {"LogDestinationConfigs": ["arn:log"], "ResourceArn": ARN}
    result = run_present(client, FakeModule(params()), current)

    assert not result.values["changed"]
    client.put_logging_configuration.assert_not_called()


def test_destination_update_preserves_unmanaged_logging_settings():
    client = Mock()
    current = {
        "LogDestinationConfigs": ["arn:old"],
        "LoggingFilter": {"DefaultBehavior": "KEEP", "Filters": []},
        "RedactedFields": [{"Method": {}}],
        "ResourceArn": ARN,
    }
    client.put_logging_configuration.return_value = {
        "LoggingConfiguration": dict(current, LogDestinationConfigs=["arn:new"])
    }
    result = run_present(client, FakeModule(params(log_destination_configs=["arn:new"])), current)

    assert result.values["changed"]
    assert result.values["logging_configuration"]["log_destination_configs"] == ["arn:new"]
    client.put_logging_configuration.assert_called_once_with(
        LoggingConfiguration={
            "LogDestinationConfigs": ["arn:new"],
            "LoggingFilter": {"DefaultBehavior": "KEEP", "Filters": []},
            "RedactedFields": [{"Method": {}}],
            "ResourceArn": ARN,
        },
        aws_retry=True,
    )


def test_absent_reports_no_change_when_configuration_disappears_during_delete():
    client = Mock()
    client.delete_logging_configuration.side_effect = nonexistent("DeleteLoggingConfiguration")
    with patch.object(plugin, "get_logging_configuration", return_value={}), pytest.raises(ModuleExit) as raised:
        plugin.ensure_absent(client, FakeModule(params(state="absent")))

    assert not raised.value.values["changed"]


def test_absent_reports_no_change_for_a_missing_web_acl():
    client = Mock(get_logging_configuration=Mock(side_effect=nonexistent("GetLoggingConfiguration")))
    with pytest.raises(ModuleExit) as raised:
        plugin.ensure_absent(client, FakeModule(params(state="absent")))

    assert not raised.value.values["changed"]
    client.delete_logging_configuration.assert_not_called()


def test_client_retries_optimistic_lock_and_service_linked_role_lock():
    module = FakeModule(params())
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin.AWSRetry, "jittered_backoff") as jittered_backoff,
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    jittered_backoff.assert_called_once_with(
        catch_extra_error_codes=["WAFOptimisticLockException", "WAFServiceLinkedRoleErrorException"]
    )
