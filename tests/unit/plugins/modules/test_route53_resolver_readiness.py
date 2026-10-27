# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from contextlib import ExitStack
from unittest.mock import ANY, Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver as endpoint
from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule as rule
from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule_associate as association
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleExit


def in_progress_case(kind, **overrides):
    """Return the plugin, params, in-progress resource, patched helpers, result key and settled resource."""
    common = dict({"name": "example", "wait": True, "wait_delay": 5, "wait_timeout": 300}, **overrides)
    if kind == "endpoint":
        plugin = endpoint
        params = dict(
            {"purge_tags": True, "tags": None},
            direction="OUTBOUND",
            resolver_endpoint_type="IPV4",
            protocols=["Do53"],
            security_group_ids=["sg-1"],
            ip_addresses=[{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
            **common,
        )
        current = {
            "Arn": "arn:endpoint",
            "Id": "rslvr-endpt-1",
            "Name": "example",
            "Status": "CREATING",
            "Direction": "OUTBOUND",
            "ResolverEndpointType": "IPV4",
            "Protocols": ["Do53"],
            "SecurityGroupIds": ["sg-1"],
            "IpAddresses": [{"SubnetId": "subnet-1"}, {"SubnetId": "subnet-2"}],
        }
        lookup = "get_resolver_endpoint_by_name"
        waiter = "wait_for_resolver_endpoint_status"
        result_key = "resolver_endpoint"
        ready = dict(current, Status="OPERATIONAL")
    elif kind == "rule":
        plugin = rule
        params = dict(
            {"purge_tags": True, "tags": None},
            domain_name="example.org",
            rule_type="FORWARD",
            resolver_endpoint_id="rslvr-endpt-1",
            target_ips=[{"ip": "10.0.0.1"}],
            **common,
        )
        current = {
            "Arn": "arn:rule",
            "Id": "rslvr-rr-1",
            "Name": "example",
            "Status": "UPDATING",
            "DomainName": "example.org.",
            "RuleType": "FORWARD",
            "ResolverEndpointId": "rslvr-endpt-1",
            "TargetIps": [{"Ip": "10.0.0.1"}],
        }
        lookup = "get_resolver_rule_by_name"
        waiter = "wait_for_resolver_rule_status"
        result_key = "resolver_rule"
        ready = dict(current, Status="COMPLETE")
    else:
        plugin = association
        params = dict(common, resolver_rule_id="rslvr-rr-1", vpc_id="vpc-1")
        current = {
            "Id": "rslvr-rrassoc-1",
            "Name": "example",
            "Status": "CREATING",
            "ResolverRuleId": "rslvr-rr-1",
            "VPCId": "vpc-1",
        }
        lookup = "get_resolver_rule_association_by_rule_and_vpc"
        waiter = "wait_for_resolver_rule_association_status"
        result_key = "resolver_rule_association"
        ready = dict(current, Status="COMPLETE")

    return plugin, params, current, lookup, waiter, result_key, ready


def run_in_progress_case(kind, check_mode, **overrides):
    plugin, params, current, lookup, waiter, result_key, ready = in_progress_case(kind, **overrides)
    client = Mock()
    module = FakeModule(params, check_mode=check_mode)
    with ExitStack() as stack:
        stack.enter_context(patch.object(plugin, lookup, side_effect=[current, ready]))
        wait = stack.enter_context(patch.object(plugin, waiter, return_value=ready))
        if kind == "endpoint":
            stack.enter_context(
                patch.object(
                    plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda client, module, resource: resource
                )
            )
            stack.enter_context(
                patch.object(
                    plugin,
                    "resolver_resource_with_tags",
                    side_effect=lambda client, module, resource, resource_type: resource,
                )
            )

        with pytest.raises(ModuleExit) as result:
            plugin.ensure_present(client, module)

    return client, module, wait, current, ready, result.value.values[result_key], result.value.values["changed"]


@pytest.mark.parametrize("kind", ["endpoint", "rule", "association"])
@pytest.mark.parametrize("wait_enabled,check_mode", [(True, False), (False, False), (True, True), (False, True)])
def test_matching_in_progress_resource_readiness(kind, wait_enabled, check_mode):
    client, module, wait, current, ready, resource, changed = run_in_progress_case(kind, check_mode, wait=wait_enabled)

    assert not changed
    if wait_enabled and not check_mode:
        # Endpoints settle first so an endpoint that needs action can be repaired,
        # and rules and associations accept FAILED here so they can be repaired.
        if kind == "endpoint":
            wait.assert_called_once_with(client, module, current["Id"], "settled", deadline=ANY)
        else:
            wait.assert_called_once_with(client, module, current["Id"], "complete", allow_failed=True, deadline=ANY)
    else:
        wait.assert_not_called()

    # Check mode predicts the settled status a waited real run returns; without a wait both keep the observed one.
    assert resource["status"] == (ready["Status"] if wait_enabled else current["Status"])
    assert client.mock_calls == []


@pytest.mark.parametrize("kind", ["endpoint", "rule"])
@pytest.mark.parametrize("check_mode", [False, True])
def test_in_progress_resource_with_a_tag_change_returns_the_settled_status(kind, check_mode):
    # Even without wait, a real run waits for an in-progress resource to settle before changing it.
    client, module, wait, current, ready, resource, changed = run_in_progress_case(
        kind, check_mode, tags={"Name": "example"}, wait=False
    )

    assert changed
    assert resource["status"] == ready["Status"]
    assert resource["tags"] == {"Name": "example"}
    if check_mode:
        wait.assert_not_called()
        assert client.mock_calls == []
    else:
        if kind == "endpoint":
            wait.assert_called_once_with(client, module, current["Id"], "settled", deadline=ANY)
        else:
            wait.assert_called_once_with(client, module, current["Id"], "complete", allow_failed=True, deadline=ANY)

        client.tag_resource.assert_called_once()
