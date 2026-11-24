from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import wafv2_web_acl_logging as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    assert_module_contract,
)

ARN = "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/main/acl-1"
WEB_ACL = {"Id": "acl-1", "Name": "main", "Scope": "REGIONAL"}


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
        patch.object(
            plugin, "ensure_present", side_effect=lambda client, module, web_acl: module.exit_json(web_acl=web_acl)
        ),
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
        plugin.ensure_present(client, module, WEB_ACL)

    return raised.value


def test_module_contract():
    captured = assert_module_contract(plugin)

    assert captured["required_if"] == [("state", "present", ["log_destination_configs"])]


@pytest.mark.parametrize(
    ("resource_arn", "web_acl"),
    [
        (ARN, WEB_ACL),
        # AWS WAFv2 rejects a web ACL ARN from another region with WAFInvalidParameterException on the first read.
        (
            "arn:aws:wafv2:us-west-2:123456789012:regional/webacl/main/acl-1",
            {"Id": "acl-1", "Name": "main", "Scope": "REGIONAL"},
        ),
        (
            "arn:aws:wafv2:us-east-1:123456789012:global/webacl/edge/acl-2",
            {"Id": "acl-2", "Name": "edge", "Scope": "CLOUDFRONT"},
        ),
    ],
)
def test_web_acl_identity_is_read_from_the_arn(resource_arn, web_acl):
    result, require_client_methods = run_main(FakeModule(params(resource_arn=resource_arn), client=Mock()))

    assert result.values["web_acl"] == web_acl
    assert require_client_methods.call_args.args[3]["get_web_acl"] == ("Id", "Name", "Scope")


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
def test_unusable_arn_fails_before_aws(resource_arn, message):
    result, require_client_methods = run_main(FakeModule(params(resource_arn=resource_arn), client=Mock()))

    assert result.values["msg"] == message
    require_client_methods.assert_not_called()


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
    client.get_web_acl.assert_called_once_with(**WEB_ACL, aws_retry=True)
    client.put_logging_configuration.assert_not_called()


def test_check_mode_predicts_the_stored_configuration_a_put_returns():
    current = {
        "LogDestinationConfigs": ["arn:old"],
        "LogScope": "CUSTOMER",
        "LogType": "WAF_LOGS",
        "LoggingFilter": {"DefaultBehavior": "KEEP", "Filters": []},
        "ManagedByFirewallManager": False,
        "ResourceArn": ARN,
    }
    stored = dict(current, LogDestinationConfigs=["arn:new"])
    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.put_logging_configuration.return_value = {"LoggingConfiguration": stored}
        results[check_mode] = run_present(
            client, FakeModule(params(log_destination_configs=["arn:new"]), check_mode=check_mode), current
        ).values

    assert results[True] == results[False]


@pytest.mark.parametrize("check_mode", [False, True])
def test_missing_web_acl_fails_before_logging_is_put(check_mode):
    client = Mock()
    client.get_web_acl.side_effect = nonexistent("GetWebACL")
    result = run_present(client, FakeModule(params(), check_mode=check_mode), None)

    assert result.values["msg"] == f"AWS WAFv2 web ACL {ARN} does not exist"
    client.put_logging_configuration.assert_not_called()


def test_existing_logging_configuration_skips_the_web_acl_lookup():
    client = Mock()
    current = {"LogDestinationConfigs": ["arn:log"], "ResourceArn": ARN}
    result = run_present(client, FakeModule(params()), current)

    assert not result.values["changed"]
    client.get_web_acl.assert_not_called()


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


@pytest.mark.parametrize("check_mode", [False, True])
def test_absent_deletes_an_existing_configuration(check_mode):
    client = Mock()
    current = {"LogDestinationConfigs": ["arn:log"], "ResourceArn": ARN}
    with (
        patch.object(plugin, "get_logging_configuration", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, FakeModule(params(state="absent"), check_mode=check_mode))

    assert raised.value.values == {"changed": True, "resource_arn": ARN, "state": "absent"}
    if check_mode:
        client.delete_logging_configuration.assert_not_called()
    else:
        client.delete_logging_configuration.assert_called_once_with(ResourceArn=ARN, aws_retry=True)


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
