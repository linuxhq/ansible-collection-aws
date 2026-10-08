from unittest.mock import Mock, patch

import pytest
from botocore.session import get_session

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

from ansible_collections.linuxhq.aws.plugins.module_utils import route53_resolver as route53_resolver_utils
from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


@pytest.mark.parametrize("check_mode", [False, True])
def test_equivalent_ipv6_target_is_idempotent(check_mode):
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "main",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "tags": None,
            "target_ips": [{"ipv6": "2001:0DB8:0000:0000:0000:0000:0000:0010"}],
            "wait": False,
        },
        check_mode=check_mode,
    )
    current = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-1",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ipv6": "2001:db8::10", "Port": 53, "Protocol": "Do53"}],
    }
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    assert raised.value.values["resolver_rule"]["target_ips"][0]["ipv6"] == "2001:db8::10"
    assert not client.mock_calls


def test_get_rejects_malformed_response():
    client = Mock(get_resolver_rule=Mock(return_value=[]))
    with pytest.raises(ModuleFail) as raised:
        plugin.get_resolver_rule(client, FakeModule({"name": "rule"}), "rslvr-rr-1")

    assert raised.value.values["msg"] == "get_resolver_rule: AWS returned an invalid resolver rule"


def test_create_rereads_rule_when_response_is_lean():
    client = Mock(create_resolver_rule=Mock(return_value={}))
    module = FakeModule({"state": "present", "tags": None, "wait": False})
    request = {
        "DomainName": "example.com",
        "Name": "main",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    rule = {"Id": "rslvr-rr-1"}
    with patch.object(plugin, "get_resolver_rule_by_name", return_value=rule) as get:
        result = plugin.create_resolver_rule(client, module, request)

    get.assert_called_once_with(client, module, changed=True)
    assert result["DomainName"] == "example.com"
    assert result["Id"] == "rslvr-rr-1"


def test_list_by_name_rejects_malformed_rule():
    module = FakeModule({"name": "main", "state": "absent"})
    with (
        patch.object(plugin, "query_list", return_value=[{"Name": "main"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_resolver_rule_by_name(Mock(), module)

    assert "without a valid ID" in raised.value.values["msg"]


def test_rule_and_tag_validation_rejects_malformed_entries():
    module = FakeModule({"name": "main"})
    rule = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-1",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Port": 53}],
    }
    with pytest.raises(ModuleFail) as target_raised:
        plugin.validate_resolver_rule(module, rule, "get_resolver_rule", require_details=True)

    assert "without an IP address" in target_raised.value.values["msg"]

    with pytest.raises(ModuleFail) as tag_raised:
        route53_resolver_utils.validate_tags(module, [{"Key": "Name"}])

    assert "invalid tag" in tag_raised.value.values["msg"]


def test_absent_waits_for_deleting_rule_without_deleting_again():
    client = Mock()
    module = FakeModule({"name": "rule", "wait": True})
    rule = {"Id": "rslvr-rr-1", "Status": "DELETING"}
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=rule),
        patch.object(plugin, "delete_resolver_rule") as delete,
        patch.object(plugin, "wait_for_resolver_rule_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert not raised.value.values["changed"]
    delete.assert_not_called()
    wait.assert_called_once_with(client, module, "rslvr-rr-1", "deleted")


def test_delete_waits_when_requested():
    client = Mock()
    module = FakeModule({"name": "rule", "wait": True})
    with patch.object(plugin, "wait_for_resolver_rule_status") as wait:
        plugin.delete_resolver_rule(client, module, {"Id": "rslvr-rr-1"})

    wait.assert_called_once_with(client, module, "rslvr-rr-1", "deleted", changed=True)


def test_delete_tolerates_rule_disappearing():
    client = Mock()
    client.delete_resolver_rule.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteResolverRule",
    )
    module = FakeModule({"name": "rule", "wait": True})
    with patch.object(plugin, "wait_for_resolver_rule_status") as wait:
        plugin.delete_resolver_rule(client, module, {"Id": "rslvr-rr-1"})

    wait.assert_not_called()


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["rule_type"]["choices"] == ["FORWARD"]
    assert options["argument_spec"]["target_ips"]["required_one_of"] == [["ip", "ipv6"]]


def test_rule_type_choices_are_sdk_values():
    spec = assert_module_contract(plugin)["argument_spec"]
    model = get_session().get_service_model("route53resolver")

    assert set(spec["rule_type"]["choices"]) <= set(model.shape_for("RuleTypeOption").enum)


@pytest.mark.parametrize("rule_type", ["forward", "Forward"])
def test_lowercase_rule_type_is_rejected(rule_type):
    spec = assert_module_contract(plugin)
    spec.pop("supports_check_mode")

    result = ArgumentSpecValidator(**spec).validate(rule_params(rule_type=rule_type))

    assert any("rule_type" in message for message in result.error_messages)


def test_empty_tags_do_not_gate_tag_resource():
    client = Mock()
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "rule",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "state": "present",
            "tags": {},
            "target_ips": [{"ip": "192.0.2.1", "port": 53}],
            "wait": False,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "ensure_present"),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "require_positive_wait_bounds"),
    ):
        plugin.main()

    methods = require_methods.call_args.args[3]
    assert "tag_resource" not in methods
    assert "untag_resource" in methods


def test_omitted_tags_do_not_gate_create_tags_parameter():
    client = Mock()
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "rule",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "state": "present",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1", "port": 53}],
            "wait": False,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "ensure_present"),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "require_positive_wait_bounds"),
    ):
        plugin.main()

    methods = require_methods.call_args.args[3]
    assert "Tags" not in methods["create_resolver_rule"]


def test_empty_target_ips_are_rejected():
    assert_module_rejects(
        plugin,
        {
            "domain_name": "example.com",
            "name": "rule",
            "resolver_endpoint_id": "rslvr-out-1",
            "state": "present",
            "tags": None,
            "target_ips": [],
        },
        "target_ips must contain at least one entry",
    )


def test_invalid_name_is_rejected_when_absent():
    assert_module_rejects(
        plugin,
        {"name": "123", "state": "absent", "tags": None},
        "name must be a valid resolver rule name of at most 64 characters",
    )


def test_no_wait_present_still_validates_internal_wait_bounds():
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "rule",
            "resolver_endpoint_id": "rslvr-out-1",
            "state": "present",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1", "port": 53}],
            "wait": False,
            "wait_delay": 0,
            "wait_timeout": 300,
        },
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "wait_delay must be 1 or greater"


def test_replacement_sensitive_limits_are_rejected():
    base = {
        "domain_name": "example.com",
        "name": "rule",
        "resolver_endpoint_id": "rslvr-out-1",
        "state": "present",
        "tags": None,
        "target_ips": [{"ip": "192.0.2.1", "port": 53}],
    }
    cases = (
        (
            dict(base, name="123"),
            "name must be a valid resolver rule name of at most 64 characters",
        ),
        (
            dict(base, domain_name=""),
            "domain_name must contain 1 to 256 characters",
        ),
        (
            dict(base, resolver_endpoint_id=""),
            "resolver_endpoint_id must contain 1 to 64 characters",
        ),
        (
            dict(base, tags={str(index): "" for index in range(201)}),
            "tags must contain at most 200 entries",
        ),
        (
            dict(
                base,
                target_ips=[
                    {
                        "ip": "192.0.2.1",
                        "port": 53,
                        "server_name_indication": "s" * 256,
                    }
                ],
            ),
            "target_ips[].server_name_indication must contain at most 255 characters",
        ),
    )
    for params, message in cases:
        assert_module_rejects(plugin, params, message)


def test_target_port_bounds_are_rejected():
    assert_module_rejects(
        plugin,
        {
            "domain_name": "example.com",
            "name": "rule",
            "resolver_endpoint_id": "rslvr-out-1",
            "state": "present",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1", "port": 65536}],
        },
        "target_ips[].port must be between 0 and 65535",
    )


def test_target_ip_versions_are_rejected():
    for target, message in (
        (
            {"ip": "2001:db8::1", "port": 53},
            "target_ips[].ip must be a valid IPv4 address",
        ),
        (
            {"ipv6": "192.0.2.1", "port": 53},
            "target_ips[].ipv6 must be a valid IPv6 address",
        ),
    ):
        assert_module_rejects(
            plugin,
            {
                "domain_name": "example.com",
                "name": "rule",
                "resolver_endpoint_id": "rslvr-out-1",
                "state": "present",
                "tags": None,
                "target_ips": [target],
            },
            message,
        )


def test_rule_comparison_normalizes_domain_without_adding_target_defaults():
    assert plugin.comparable_rule(
        {
            "DomainName": "Example.COM.",
            "ResolverEndpointId": "rslvr-out-1",
            "RuleType": "FORWARD",
            "TargetIps": [{"Ip": "192.0.2.1"}],
        }
    ) == {
        "domain_name": "example.com",
        "resolver_endpoint_id": "rslvr-out-1",
        "rule_type": "FORWARD",
        "target_ips": [{"ip": "192.0.2.1"}],
    }


def test_create_token_changes_with_desired_rule():
    client = Mock(
        create_resolver_rule=Mock(
            side_effect=[
                {"ResolverRule": {"Id": "rule-1"}},
                {"ResolverRule": {"Id": "rule-2"}},
            ]
        )
    )
    module = FakeModule({"tags": {"Env": "test"}, "wait": False})
    request = {
        "DomainName": "example.com",
        "Name": "main",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    plugin.create_resolver_rule(client, module, request)
    plugin.create_resolver_rule(client, module, dict(request, DomainName="changed.example.com"))

    calls = client.create_resolver_rule.call_args_list
    assert calls[0].kwargs["CreatorRequestId"] != calls[1].kwargs["CreatorRequestId"]
    assert calls[0].kwargs["Tags"] == [{"Key": "Env", "Value": "test"}]


def test_absent_lookup_does_not_fetch_unused_rule_details():
    client = Mock()
    module = FakeModule({"name": "main", "state": "absent"})
    summary = {"Id": "rslvr-rr-1", "Name": "main"}
    with patch.object(plugin, "query_list", return_value=[summary]):
        assert plugin.get_resolver_rule_by_name(client, module) == summary

    client.get_resolver_rule.assert_not_called()
    client.list_tags_for_resource.assert_not_called()


def test_deleting_rule_waits_before_recreation_with_final_wait_disabled():
    client = Mock()
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "main",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1"}],
            "wait": False,
        }
    )
    deleting = {"Id": "rslvr-rr-old", "Name": "main", "Status": "DELETING"}
    replacement = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-new",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    with (
        patch.object(plugin, "get_resolver_rule_by_name", side_effect=[deleting, None]),
        patch.object(plugin, "wait_for_resolver_rule_status") as wait_for_status,
        patch.object(plugin, "create_resolver_rule", return_value=replacement) as create,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait_for_status.assert_called_once_with(client, module, "rslvr-rr-old", "deleted")
    create.assert_called_once()


def test_update_rereads_rule_when_response_is_lean():
    client = Mock(update_resolver_rule=Mock(return_value={}))
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "main",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-2",
            "rule_type": "FORWARD",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1"}],
            "wait": False,
        }
    )
    current = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-1",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    updated = dict(current, ResolverEndpointId="rslvr-out-2")
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
        patch.object(plugin, "get_resolver_rule", return_value=updated) as get,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    get.assert_called_once_with(client, module, "rslvr-rr-1", changed=True)


def test_tag_change_rejects_rule_without_arn():
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "main",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-1",
            "rule_type": "FORWARD",
            "tags": {"Name": "main"},
            "target_ips": [{"ip": "192.0.2.1"}],
            "wait": False,
        }
    )
    current = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-1",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert "invalid rule ARN" in raised.value.values["msg"]


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("field,value", [("domain_name", "new.example.com"), ("rule_type", "SYSTEM")])
def test_immutable_changes_preserve_rule(check_mode, field, value):
    params = {
        "domain_name": "example.com",
        "name": "main",
        "purge_tags": True,
        "resolver_endpoint_id": "rslvr-out-1",
        "rule_type": "FORWARD",
        "tags": {"new": "value"},
        "target_ips": [{"ip": "192.0.2.1"}],
        "wait": False,
    }
    params[field] = value
    module = FakeModule(params, check_mode=check_mode)
    current = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-1",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
        patch.object(plugin, "delete_resolver_rule") as delete,
        patch.object(plugin, "create_resolver_rule") as create,
        pytest.raises(ModuleFail, match=field),
    ):
        plugin.ensure_present(client, module)

    delete.assert_not_called()
    create.assert_not_called()
    assert not client.mock_calls


@pytest.mark.parametrize("wait", [False, True])
def test_update_mismatch_preserves_rule(wait):
    module = FakeModule(
        {
            "domain_name": "example.com",
            "name": "main",
            "purge_tags": True,
            "resolver_endpoint_id": "rslvr-out-2",
            "rule_type": "FORWARD",
            "tags": None,
            "target_ips": [{"ip": "192.0.2.1"}],
            "wait": wait,
        }
    )
    current = {
        "DomainName": "example.com",
        "Id": "rslvr-rr-1",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1"}],
    }
    client = Mock(update_resolver_rule=Mock(return_value={"ResolverRule": current}))
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=current),
        patch.object(plugin, "get_resolver_rule", return_value=current),
        patch.object(plugin, "wait_for_resolver_rule_status", return_value=current),
        patch.object(plugin, "delete_resolver_rule") as delete,
        patch.object(plugin, "create_resolver_rule") as create,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert "has not been deleted" in raised.value.values["msg"]
    client.update_resolver_rule.assert_called_once()
    delete.assert_not_called()
    create.assert_not_called()


def rule_params(**overrides):
    params = {
        "domain_name": "example.com",
        "name": "main",
        "purge_tags": True,
        "resolver_endpoint_id": "rslvr-out-1",
        "rule_type": "FORWARD",
        "state": "present",
        "tags": None,
        "target_ips": [
            {"ip": "192.0.2.1", "ipv6": None, "port": None, "protocol": None, "server_name_indication": None}
        ],
        "wait": False,
        "wait_delay": 5,
        "wait_timeout": 300,
    }
    params.update(overrides)
    return params


def existing_rule(**overrides):
    rule = {
        "Arn": "arn:rule",
        "DomainName": "example.com.",
        "Id": "rslvr-rr-1",
        "Name": "main",
        "OwnerId": "123456789012",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "ShareStatus": "NOT_SHARED",
        "Status": "COMPLETE",
        "Tags": [],
        "TargetIps": [{"Ip": "192.0.2.1", "Port": 53, "Protocol": "Do53"}],
    }
    rule.update(overrides)
    return rule


def test_requests_send_supplied_values_without_comparison_defaults():
    module = FakeModule(
        rule_params(
            domain_name=".",
            target_ips=[
                {
                    "ip": "192.0.2.1",
                    "ipv6": None,
                    "port": None,
                    "protocol": "DoH",
                    "server_name_indication": "dns.example.com",
                }
            ],
        )
    )
    assert plugin.desired_request(module) == {
        "DomainName": ".",
        "Name": "main",
        "ResolverEndpointId": "rslvr-out-1",
        "RuleType": "FORWARD",
        "TargetIps": [{"Ip": "192.0.2.1", "Protocol": "DoH", "ServerNameIndication": "dns.example.com"}],
    }


def test_omitted_target_fields_match_the_values_aws_stored():
    module = FakeModule(rule_params())
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=existing_rule()),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(Mock(), module)

    assert result.value.values["changed"] is False


def test_a_supplied_target_field_that_differs_is_a_change():
    current = plugin.comparable_rule(existing_rule())
    desired = plugin.comparable_rule(dict(existing_rule(), TargetIps=[{"Ip": "192.0.2.1", "Port": 5353}]))
    assert not plugin.rules_match(current, desired)


def test_waiting_for_a_complete_rule_stops_when_it_is_deleting():
    model = plugin.ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA
    complete = {a["expected"]: a["state"] for a in model["resolver_rule_complete"]["acceptors"]}
    deleted = {a["expected"]: a["state"] for a in model["resolver_rule_deleted"]["acceptors"]}
    assert complete == {"COMPLETE": "success", "UPDATING": "retry", "DELETING": "failure", "FAILED": "success"}
    assert deleted == {"ResourceNotFoundException": "success", "DELETING": "retry"}


def test_lookup_skips_shared_and_aws_owned_rules():
    owned = existing_rule()
    shared = existing_rule(Id="rslvr-rr-shared", ShareStatus="SHARED_WITH_ME", OwnerId="210987654321")
    aws_owned = existing_rule(Id="rslvr-autodefined-rr-1", OwnerId="Route 53 Resolver")
    with (
        patch.object(plugin, "query_list", return_value=[shared, owned, aws_owned]),
        patch.object(
            plugin,
            "resolver_resource_with_tags",
            side_effect=lambda client, module, rule, resource_type, changed=False: rule,
        ) as with_tags,
    ):
        assert plugin.get_resolver_rule_by_name(Mock(), FakeModule(rule_params()))["Id"] == "rslvr-rr-1"

    with_tags.assert_called_once()


def test_present_lookup_uses_the_listed_rule_without_get_resolver_rule():
    client = Mock()
    with (
        patch.object(plugin, "query_list", return_value=[existing_rule()]),
        patch.object(
            plugin,
            "resolver_resource_with_tags",
            side_effect=lambda client, module, rule, resource_type, changed=False: rule,
        ),
    ):
        plugin.get_resolver_rule_by_name(client, FakeModule(rule_params()))

    client.get_resolver_rule.assert_not_called()


def test_failed_rule_is_repaired_by_sending_the_desired_configuration():
    client = Mock()
    client.update_resolver_rule.return_value = {"ResolverRule": existing_rule(Status="UPDATING")}
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=existing_rule(Status="FAILED")),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, FakeModule(rule_params()))

    assert result.value.values["changed"] is True
    client.update_resolver_rule.assert_called_once_with(
        Config={"Name": "main", "ResolverEndpointId": "rslvr-out-1", "TargetIps": [{"Ip": "192.0.2.1"}]},
        ResolverRuleId="rslvr-rr-1",
        aws_retry=True,
    )


def test_rule_that_fails_after_a_change_reports_the_aws_status_message():
    module = FakeModule(rule_params())
    failed = existing_rule(Status="FAILED", StatusMessage="Target 192.0.2.1 is unreachable")
    with (
        patch.object(plugin, "run_waiter") as run_waiter,
        patch.object(plugin, "get_resolver_rule", return_value=failed),
        pytest.raises(ModuleFail) as result,
    ):
        plugin.wait_for_resolver_rule_status(Mock(), module, "rslvr-rr-1", "complete")

    assert run_waiter.call_args.args[4] == "Unable to wait for AWS Route53 Resolver rule main to become complete"
    assert result.value.values["msg"] == "AWS Route53 Resolver rule main failed: Target 192.0.2.1 is unreachable"


def test_delete_of_an_associated_rule_says_to_remove_associations():
    client = Mock()
    client.delete_resolver_rule.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceInUseException", "Message": "in use"}}, "DeleteResolverRule"
    )
    with pytest.raises(ModuleFail) as result:
        plugin.delete_resolver_rule(client, FakeModule(rule_params()), existing_rule())

    assert result.value.values["msg"] == (
        "Unable to delete AWS Route53 Resolver rule main: it is still associated with VPCs; remove its associations first"
    )


def test_duplicate_target_ips_are_rejected():
    target = {"ip": "192.0.2.1", "ipv6": None, "port": 53, "protocol": None, "server_name_indication": None}
    module = FakeModule(rule_params(target_ips=[target, dict(target)]))
    with patch.object(plugin, "AnsibleAWSModule", return_value=module), pytest.raises(ModuleFail) as result:
        plugin.main()

    assert result.value.values["msg"] == "target_ips entries must be unique"


def test_update_reuses_tags_read_at_the_start():
    client = Mock()
    updated = existing_rule(ResolverEndpointId="rslvr-out-2")
    updated.pop("Tags")
    client.update_resolver_rule.return_value = {"ResolverRule": updated}
    start = existing_rule(Tags=[{"Key": "Name", "Value": "main"}])
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=start),
        patch.object(plugin, "resolver_resource_with_tags") as with_tags,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(
            client, FakeModule(rule_params(resolver_endpoint_id="rslvr-out-2", tags={"Name": "main"}))
        )

    with_tags.assert_not_called()
    assert result.value.values["resolver_rule"]["tags"] == {"Name": "main"}
    client.tag_resource.assert_not_called()


def test_check_mode_tag_change_keeps_the_stored_target_values():
    module = FakeModule(rule_params(tags={"Env": "test"}), check_mode=True)
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=existing_rule()),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(Mock(), module)

    assert result.value.values["changed"] is True
    assert result.value.values["resolver_rule"]["target_ips"] == [{"ip": "192.0.2.1", "port": 53, "protocol": "Do53"}]
    assert result.value.values["resolver_rule"]["tags"] == {"Env": "test"}


def failing_waiter(module, client, model_data, waiter_name, error_msg, changed=False, **kwargs):
    module.fail_json(changed=changed, msg=error_msg)


def test_rule_that_fails_after_an_update_reports_changed():
    client = Mock()
    client.update_resolver_rule.return_value = {"ResolverRule": existing_rule(Status="UPDATING")}
    failed = existing_rule(Status="FAILED", StatusMessage="Target is unreachable")
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=existing_rule(TargetIps=[{"Ip": "192.0.2.9"}])),
        patch.object(plugin, "run_waiter"),
        patch.object(plugin, "get_resolver_rule", return_value=failed),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(rule_params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "AWS Route53 Resolver rule main failed: Target is unreachable"


def test_create_wait_failure_reports_changed():
    client = Mock(create_resolver_rule=Mock(return_value={"ResolverRule": existing_rule(Status="UPDATING")}))
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=None),
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(rule_params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to wait for AWS Route53 Resolver rule main to become complete"


def test_delete_wait_failure_reports_changed():
    with (
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.delete_resolver_rule(Mock(), FakeModule(rule_params(wait=True)), existing_rule())

    assert raised.value.values["changed"] is True


def client_error(operation):
    return plugin.ClientError({"Error": {"Code": "InternalError", "Message": "failed"}}, operation)


@pytest.mark.parametrize(("endpoint", "changed"), [("rslvr-out-2", True), ("rslvr-out-1", False)])
def test_tag_failure_reports_whether_the_rule_was_updated(endpoint, changed):
    client = Mock(tag_resource=Mock(side_effect=client_error("TagResource")))
    client.update_resolver_rule.return_value = {"ResolverRule": existing_rule(ResolverEndpointId=endpoint)}
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=existing_rule()),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(rule_params(resolver_endpoint_id=endpoint, tags={"Env": "test"})))

    assert raised.value.values["changed"] is changed
    assert client.update_resolver_rule.called is changed


def failing_query(module, client, method_name, result_key, error_msg, changed=False, **kwargs):
    module.fail_json(changed=changed, msg=error_msg)


def test_tag_listing_failure_after_create_reports_changed():
    client = Mock(create_resolver_rule=Mock(return_value={"ResolverRule": existing_rule(Status="UPDATING")}))
    with (
        patch.object(plugin, "get_resolver_rule_by_name", return_value=None),
        patch.object(plugin, "run_waiter"),
        patch.object(plugin, "get_resolver_rule", return_value=existing_rule()),
        patch.object(route53_resolver_utils, "query_list", side_effect=failing_query),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(rule_params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to list tags for AWS Route53 Resolver rule arn:rule"


def test_lookup_failure_before_create_reports_unchanged():
    client = Mock()
    with (
        patch.object(plugin, "query_list", side_effect=failing_query),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(rule_params()))

    assert raised.value.values["changed"] is False
    client.create_resolver_rule.assert_not_called()
