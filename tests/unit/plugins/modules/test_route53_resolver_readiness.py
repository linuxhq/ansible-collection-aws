# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from contextlib import ExitStack
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver as endpoint
from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule as rule
from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver_rule_associate as association
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleExit


@pytest.mark.parametrize("kind", ["endpoint", "rule", "association"])
@pytest.mark.parametrize("wait_enabled,check_mode", [(True, False), (False, False), (True, True)])
def test_matching_in_progress_resource_readiness(kind, wait_enabled, check_mode):
    common = {"name": "example", "wait": wait_enabled, "tags": None, "purge_tags": True}
    if kind == "endpoint":
        plugin = endpoint
        params = dict(
            common,
            direction="outbound",
            resolver_endpoint_type="ipv4",
            protocols=["do53"],
            security_group_ids=["sg-1"],
            ip_addresses=[{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
        )
        current = {
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
            common,
            domain_name="example.org",
            rule_type="forward",
            resolver_endpoint_id="rslvr-endpt-1",
            target_ips=[{"ip": "10.0.0.1"}],
        )
        current = {
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
                    plugin, "resolver_endpoint_with_tags", side_effect=lambda client, module, resource: resource
                )
            )

        with pytest.raises(ModuleExit) as result:
            plugin.ensure_present(client, module)

    assert not result.value.values["changed"]
    if wait_enabled and not check_mode:
        wait.assert_called_once_with(client, module, current["Id"], {ready["Status"].lower()})
        assert result.value.values[result_key]["status"] == ready["Status"]
    else:
        wait.assert_not_called()
        assert result.value.values[result_key]["status"] == current["Status"]

    assert client.mock_calls == []
