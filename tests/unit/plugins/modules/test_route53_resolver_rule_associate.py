from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule_associate as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

ASSOCIATION = {
    "Id": "rslvr-rrassoc-1",
    "Name": "main",
    "ResolverRuleId": "rslvr-rr-1",
    "Status": "COMPLETE",
    "VPCId": "vpc-1",
}


def params(**overrides):
    values = {
        "name": "main",
        "resolver_rule_id": "rslvr-rr-1",
        "state": "present",
        "vpc_id": "vpc-1",
        "wait": False,
        "wait_delay": 5,
        "wait_timeout": 300,
    }
    values.update(overrides)
    return values


def acceptors(waiter_name):
    return {
        acceptor["expected"]: acceptor["state"]
        for acceptor in plugin.ROUTE53_RESOLVER_RULE_ASSOCIATION_WAITER_MODEL_DATA[waiter_name]["acceptors"]
    }


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["argument_spec"]["wait_timeout"]["default"] == 300
    assert "required_if" not in captured
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_complete_waiter_stops_on_deleting_and_returns_failed_for_inspection():
    assert acceptors("resolver_rule_association_complete") == {
        "COMPLETE": "success",
        "CREATING": "retry",
        "DELETING": "failure",
        "FAILED": "success",
        "OVERRIDDEN": "success",
    }


def test_deleted_waiter_stops_on_failed():
    assert acceptors("resolver_rule_association_deleted") == {
        "DELETING": "retry",
        "FAILED": "failure",
        "ResourceNotFoundException": "success",
    }


@pytest.mark.parametrize("state", ["complete", "deleted"])
def test_wait_message_names_the_target_state(state):
    module = FakeModule(params())
    with patch.object(plugin, "run_waiter") as run_waiter:
        run_waiter.side_effect = ModuleFail({})
        with pytest.raises(ModuleFail):
            plugin.wait_for_resolver_rule_association_status(Mock(), module, "rslvr-rrassoc-1", state)

    assert run_waiter.call_args.args[3] == f"resolver_rule_association_{state}"
    assert run_waiter.call_args.args[4] == (
        f"Unable to wait for AWS Route53 Resolver rule association main to become {state}"
    )


def test_wait_fails_with_status_message_when_association_failed():
    client = Mock()
    client.get_resolver_rule_association.return_value = {
        "ResolverRuleAssociation": dict(ASSOCIATION, Status="FAILED", StatusMessage="VPC is gone")
    }
    with patch.object(plugin, "run_waiter"), pytest.raises(ModuleFail) as raised:
        plugin.wait_for_resolver_rule_association_status(client, FakeModule(params()), "rslvr-rrassoc-1", "complete")

    assert raised.value.values["msg"] == "AWS Route53 Resolver rule association main failed: VPC is gone"
    assert raised.value.values["resolver_rule_association"]["status"] == "FAILED"


def test_wait_returns_failed_association_when_allowed():
    client = Mock()
    client.get_resolver_rule_association.return_value = {"ResolverRuleAssociation": dict(ASSOCIATION, Status="FAILED")}
    with patch.object(plugin, "run_waiter"):
        association = plugin.wait_for_resolver_rule_association_status(
            client, FakeModule(params()), "rslvr-rrassoc-1", "complete", allow_failed=True
        )

    assert association["Status"] == "FAILED"


def test_wait_rejects_malformed_get_response():
    client = Mock(get_resolver_rule_association=Mock(return_value=[]))
    with patch.object(plugin, "run_waiter"), pytest.raises(ModuleFail) as raised:
        plugin.wait_for_resolver_rule_association_status(client, FakeModule(params()), "rslvr-rrassoc-1", "complete")

    assert "invalid resolver rule association" in raised.value.values["msg"]


@pytest.mark.parametrize("name", [None, "main"])
def test_failed_association_is_replaced(name):
    client = Mock()
    client.associate_resolver_rule.return_value = {
        "ResolverRuleAssociation": {"Id": "rslvr-rrassoc-2", "ResolverRuleId": "rslvr-rr-1", "VPCId": "vpc-1"}
    }
    failed = dict(ASSOCIATION, Status="FAILED")
    module = FakeModule(params(name=name))
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=failed),
        patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    client.disassociate_resolver_rule.assert_called_once_with(
        ResolverRuleId="rslvr-rr-1", VPCId="vpc-1", aws_retry=True
    )
    wait_for_status.assert_called_once_with(client, module, "rslvr-rrassoc-1", "deleted", changed=True)
    # An omitted name keeps the failed association's name.
    client.associate_resolver_rule.assert_called_once_with(
        Name="main", ResolverRuleId="rslvr-rr-1", VPCId="vpc-1", aws_retry=True
    )
    assert raised.value.values["resolver_rule_association_id"] == "rslvr-rrassoc-2"


def test_failed_association_replacement_is_predicted_in_check_mode():
    client = Mock()
    failed = dict(ASSOCIATION, Status="FAILED")
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=failed),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(name=None), check_mode=True))

    assert raised.value.values["changed"]
    assert raised.value.values["resolver_rule_association"]["name"] == "main"
    assert "resolver_rule_association_id" not in raised.value.values
    client.disassociate_resolver_rule.assert_not_called()
    client.associate_resolver_rule.assert_not_called()


def test_creating_association_wait_allows_failed_so_it_can_be_replaced():
    client = Mock()
    client.associate_resolver_rule.return_value = {"ResolverRuleAssociation": dict(ASSOCIATION, Id="rslvr-rrassoc-2")}
    creating = dict(ASSOCIATION, Status="CREATING")
    with (
        patch.object(
            plugin,
            "get_resolver_rule_association_by_rule_and_vpc",
            side_effect=[creating, dict(ASSOCIATION, Status="FAILED")],
        ),
        patch.object(
            plugin,
            "wait_for_resolver_rule_association_status",
            return_value=dict(ASSOCIATION, Id="rslvr-rrassoc-2"),
        ) as wait_for_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(wait=True)))

    assert wait_for_status.call_args_list[0].args[2:] == ("rslvr-rrassoc-1", "complete")
    assert wait_for_status.call_args_list[0].kwargs == {"allow_failed": True}
    assert raised.value.values["changed"]
    client.disassociate_resolver_rule.assert_called_once()


def test_create_rereads_association_when_response_is_lean():
    client = Mock(associate_resolver_rule=Mock(return_value={}))
    association = {"Id": "rslvr-rrassoc-1", "Name": "main", "ResolverRuleId": "rslvr-rr-1", "VPCId": "vpc-1"}
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", side_effect=[None, association]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params()))

    assert raised.value.values["resolver_rule_association_id"] == "rslvr-rrassoc-1"


@pytest.mark.parametrize(
    ("associations", "message"),
    [
        ([{"Name": "main", "ResolverRuleId": "rslvr-rr-1", "VPCId": "vpc-1"}], "without a valid ID"),
        (
            [dict(ASSOCIATION, Id="rslvr-rrassoc-1"), dict(ASSOCIATION, Id="rslvr-rrassoc-2")],
            "Multiple AWS Route53 Resolver rule associations",
        ),
        ([dict(ASSOCIATION, VPCId="vpc-2")], "unexpected resolver rule association VPCId"),
    ],
)
def test_list_rejects_malformed_and_ambiguous_associations(associations, message):
    with patch.object(plugin, "query_list", return_value=associations), pytest.raises(ModuleFail) as raised:
        plugin.get_resolver_rule_association_by_rule_and_vpc(Mock(), FakeModule(params()))

    assert message in raised.value.values["msg"]
    assert raised.value.values["changed"] is False


def test_ambiguous_lookup_after_create_reports_changed():
    client = Mock(associate_resolver_rule=Mock(return_value={}))
    duplicates = [dict(ASSOCIATION, Id="rslvr-rrassoc-1"), dict(ASSOCIATION, Id="rslvr-rrassoc-2")]
    with (
        patch.object(plugin, "query_list", side_effect=[[], duplicates]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params()))

    assert "Multiple AWS Route53 Resolver rule associations" in raised.value.values["msg"]
    assert raised.value.values["changed"] is True


def test_check_mode_replacement_does_not_return_stale_id():
    current = dict(ASSOCIATION, Id="old-association", Name="old-name")
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), FakeModule(params(name="new-name", wait=True), check_mode=True))

    assert raised.value.values["changed"]
    assert "resolver_rule_association_id" not in raised.value.values


def test_check_mode_predicts_rule_association():
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), FakeModule(params(wait=True), check_mode=True))

    assert raised.value.values["changed"]
    assert raised.value.values["resolver_rule_association"]["vpc_id"] == "vpc-1"


def test_absent_does_not_require_name():
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(Mock(), FakeModule(params(name=None, state="absent")))

    assert not raised.value.values["changed"]
    assert "name" not in raised.value.values


def test_absent_tolerates_association_disappearing_during_delete():
    client = Mock()
    client.disassociate_resolver_rule.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DisassociateResolverRule",
    )
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=ASSOCIATION),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, FakeModule(params(state="absent")))

    assert raised.value.values["changed"]


def test_absent_waits_for_deleting_association_without_disassociating():
    client = Mock()
    module = FakeModule(params(name=None, state="absent", wait=True))
    with (
        patch.object(
            plugin,
            "get_resolver_rule_association_by_rule_and_vpc",
            return_value=dict(ASSOCIATION, Status="DELETING"),
        ),
        patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert not raised.value.values["changed"]
    client.disassociate_resolver_rule.assert_not_called()
    wait_for_status.assert_called_once_with(client, module, "rslvr-rrassoc-1", "deleted", changed=False)


def test_omitted_name_keeps_an_existing_association():
    client = Mock()
    current = dict(ASSOCIATION, Name="existing")
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(name=None)))

    assert not raised.value.values["changed"]
    assert "name" not in raised.value.values
    client.disassociate_resolver_rule.assert_not_called()
    client.associate_resolver_rule.assert_not_called()


def test_new_association_without_name_omits_it_from_the_request():
    client = Mock()
    client.associate_resolver_rule.return_value = {
        "ResolverRuleAssociation": {"Id": "rslvr-rrassoc-1", "ResolverRuleId": "rslvr-rr-1", "VPCId": "vpc-1"}
    }
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(name=None)))

    assert raised.value.values["changed"]
    client.associate_resolver_rule.assert_called_once_with(ResolverRuleId="rslvr-rr-1", VPCId="vpc-1", aws_retry=True)


def test_replacement_waits_for_deletion_when_final_wait_is_disabled():
    client = Mock()
    client.associate_resolver_rule.return_value = {"ResolverRuleAssociation": {"Id": "new-association"}}
    module = FakeModule(params(name="new-name"))
    current = dict(ASSOCIATION, Id="old-association", Name="old-name", Status="OVERRIDDEN")
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=current),
        patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait_for_status.assert_called_once_with(client, module, "old-association", "deleted", changed=True)


def test_deleting_association_waits_before_recreation():
    client = Mock()
    client.associate_resolver_rule.return_value = {"ResolverRuleAssociation": {"Id": "new-association"}}
    module = FakeModule(params())
    deleting = {"Id": "old-association", "Status": "DELETING"}
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", side_effect=[deleting, None]),
        patch.object(plugin, "wait_for_resolver_rule_association_status") as wait_for_status,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait_for_status.assert_called_once_with(client, module, "old-association", "deleted")
    client.associate_resolver_rule.assert_called_once()


def test_present_validates_bounds_for_internal_replacement_wait():
    module = FakeModule(params(wait_delay=0))
    with patch.object(plugin, "AnsibleAWSModule", return_value=module), pytest.raises(ModuleFail) as raised:
        plugin.main()

    assert "wait_delay" in raised.value.values["msg"]


def test_present_rejects_invalid_name_before_api_calls():
    module = FakeModule(params(name="123"))
    with patch.object(plugin, "AnsibleAWSModule", return_value=module), pytest.raises(ModuleFail) as raised:
        plugin.main()

    assert "valid resolver rule association name" in raised.value.values["msg"]


def test_association_that_fails_after_creation_reports_changed():
    client = Mock()
    client.associate_resolver_rule.return_value = {"ResolverRuleAssociation": dict(ASSOCIATION, Status="CREATING")}
    client.get_resolver_rule_association.return_value = {
        "ResolverRuleAssociation": dict(ASSOCIATION, Status="FAILED", StatusMessage="VPC is gone")
    }
    with (
        patch.object(plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=None),
        patch.object(plugin, "run_waiter"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "AWS Route53 Resolver rule association main failed: VPC is gone"


@pytest.mark.parametrize("state", ["absent", "present"])
def test_disassociation_wait_failure_reports_changed(state):
    def failing_waiter(module, client, model_data, waiter_name, error_msg, changed=False, **kwargs):
        module.fail_json(changed=changed, msg=error_msg)

    ensure = plugin.ensure_absent if state == "absent" else plugin.ensure_present
    with (
        patch.object(
            plugin, "get_resolver_rule_association_by_rule_and_vpc", return_value=dict(ASSOCIATION, Status="FAILED")
        ),
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        ensure(Mock(), FakeModule(params(state=state, wait=True)))

    assert raised.value.values["changed"] is True
    assert (
        raised.value.values["msg"] == "Unable to wait for AWS Route53 Resolver rule association main to become deleted"
    )
