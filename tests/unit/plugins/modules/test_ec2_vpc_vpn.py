# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, WaiterError
from botocore.session import Session
from botocore.validate import validate_parameters

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

from ansible_collections.amazon.aws.plugins.module_utils.retries import RetryingBotoClientWrapper

from ansible_collections.linuxhq.aws.plugins.modules import ec2_vpc_vpn as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleExit, ModuleFail


@pytest.fixture
def connection():
    return {
        "VpnConnectionId": "vpn-123",
        "State": "available",
        "CustomerGatewayId": "cgw-123",
        "VpnGatewayId": "vgw-123",
        "Type": "ipsec.1",
        "CustomerGatewayConfiguration": "<xml>EXAMPLE_GENERATED_SECRET</xml>",
        "Tags": [{"Key": "Name", "Value": "branch"}, {"Key": "OwnerTeam", "Value": "NetworkOps"}],
        "Options": {
            "StaticRoutesOnly": True,
            "TunnelInsideIpVersion": "ipv4",
            "LocalIpv4NetworkCidr": "0.0.0.0/0",
            "TunnelOptions": [
                {
                    "OutsideIpAddress": "203.0.113.1",
                    "PreSharedKey": "EXAMPLE_GENERATED_SECRET",
                    "Phase1EncryptionAlgorithms": [{"Value": "AES128"}, {"Value": "AES256"}],
                },
                {
                    "OutsideIpAddress": "203.0.113.2",
                    "PreSharedKey": "EXAMPLE_SECOND_SECRET",
                    "Phase1EncryptionAlgorithms": [{"Value": "AES128"}],
                },
            ],
        },
        "Routes": [{"DestinationCidrBlock": "10.0.0.0/8", "State": "available"}],
    }


@pytest.fixture
def module_spec():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleExit({})

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleExit):
        plugin.main()

    assert captured["supports_check_mode"]
    return captured


@pytest.mark.parametrize("target", ["available", "deleted"])
@pytest.mark.parametrize("vpn_state", ["deleting", "deleted", "missing", "not_found"])
def test_route_waiter_fails_immediately_when_vpn_is_gone(params, target, vpn_state):
    params.update(wait_delay=1, wait_timeout=600)
    client = Session().create_client(
        "ec2", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    response = {"VpnConnections": [] if vpn_state == "missing" else [{"State": vpn_state, "Routes": []}]}
    describe = Mock(return_value=response)
    if vpn_state == "not_found":
        describe.side_effect = ClientError(
            {"Error": {"Code": "InvalidVpnConnectionID.NotFound", "Message": "VPN is missing"}},
            "DescribeVpnConnections",
        )

    with (
        patch.object(client, "describe_vpn_connections", describe),
        patch("botocore.waiter.time.sleep") as sleep,
        pytest.raises(ModuleFail, match="Unable to wait for route"),
    ):
        plugin.wait_for_route_state(client, FakeModule(params), "vpn-123", "10.0.0.0/8", target)

    describe.assert_called_once_with(VpnConnectionIds=["vpn-123"])
    sleep.assert_not_called()


def test_available_route_waiter_times_out_on_persistent_deleted_target(params):
    params.update(wait_delay=1, wait_timeout=1)
    client = Session().create_client(
        "ec2", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    describe = Mock(
        return_value={
            "VpnConnections": [
                {"State": "available", "Routes": [{"DestinationCidrBlock": "10.0.0.0/8", "State": "deleted"}]}
            ]
        }
    )
    with (
        patch.object(client, "describe_vpn_connections", describe),
        patch("botocore.waiter.time.sleep") as sleep,
        pytest.raises(ModuleFail, match="to become available"),
    ):
        plugin.wait_for_route_available(client, FakeModule(params), "vpn-123", "10.0.0.0/8")

    assert describe.call_count == 2
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("with_pending", [True, False])
def test_route_recreation_waits_through_stale_deleted_entry(params, with_pending):
    params.update(wait_delay=1, wait_timeout=2)
    client = Session().create_client(
        "ec2", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    deleted = {"DestinationCidrBlock": "10.0.0.0/8", "State": "deleted"}
    pending = dict(deleted, State="pending")
    available = dict(deleted, State="available")
    describe = Mock(
        side_effect=[
            {"VpnConnections": [{"State": "available", "Routes": [deleted]}]},
            {"VpnConnections": [{"State": "available", "Routes": [deleted, pending] if with_pending else [deleted]}]},
            {"VpnConnections": [{"State": "available", "Routes": [deleted, available]}]},
        ]
    )
    module = FakeModule(params)
    with (
        patch.object(client, "describe_vpn_connections", describe),
        patch.object(client, "create_vpn_connection_route") as create,
        patch("botocore.waiter.time.sleep") as sleep,
    ):
        plugin.wait_for_route_deleted(client, module, "vpn-123", "10.0.0.0/8")
        plugin.reconcile_routes(client, module, "vpn-123", {"10.0.0.0/8"}, set())

    assert describe.call_count == 3
    create.assert_called_once_with(VpnConnectionId="vpn-123", DestinationCidrBlock="10.0.0.0/8", aws_retry=True)
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("selector, value", [("vpn_connection_id", "vpn-missing"), ("filters", {"state": "available"})])
@pytest.mark.parametrize("check_mode", [True, False])
def test_unmatched_selector_reports_lookup_failure(params, selector, value, check_mode):
    params.update(name=None, **{selector: value})
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": []}
    module = FakeModule(params, check_mode=check_mode)
    found = plugin.find_connection(client, module)
    with pytest.raises(ModuleFail, match=f"No VPN connection matched {selector}"):
        plugin.ensure_present(client, module, found)

    client.create_vpn_connection.assert_not_called()


@pytest.mark.parametrize("current", [None, [], [{}, {}], [{"OutsideIpAddress": "203.0.113.1"}, {}]])
@pytest.mark.parametrize(
    "desired",
    [
        [{"phase1_encryption_algorithms": ["AES256"]}],
        [{"phase1_encryption_algorithms": ["AES256"]}, {"phase1_encryption_algorithms": ["AES128"]}],
        [{"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256"]}],
        [],
    ],
)
def test_pending_vpn_check_mode_predicts_unallocated_tunnels(params, connection, current, desired):
    connection["State"] = "pending"
    connection["Options"]["TunnelOptions"] = current
    params["tunnel_options"] = desired
    module = FakeModule(params, check_mode=True)
    client = Mock()
    plugin.validate_inputs(module)
    with patch.object(plugin, "wait_for_connection") as waiter, pytest.raises(ModuleExit) as result:
        plugin.ensure_present(client, module, connection)

    assert result.value.values["changed"] is bool(desired)
    assert result.value.values["vpn_connection"]["state"] == "pending"
    assert "customer_gateway_configuration" not in result.value.values["vpn_connection"]
    assert client.mock_calls == []
    waiter.assert_not_called()


@pytest.mark.parametrize(
    "desired, message",
    [
        ([{"tunnel_inside_cidr": "169.254.10.0/30"}], "Select a specific tunnel"),
        ([{"outside_ip_address": "203.0.113.1"}, {}], "Do not mix"),
        ([{"outside_ip_address": "203.0.113.1"}, {"outside_ip_address": "203.0.113.1"}], "distinct"),
        ([{"pre_shared_key": "bad"}], "Invalid tunnel pre_shared_key"),
        ([{"phase1_encryption_algorithms": []}], "must not be empty"),
    ],
)
def test_pending_vpn_check_mode_still_validates_inputs(params, connection, desired, message):
    connection["State"] = "pending"
    connection["Options"]["TunnelOptions"] = []
    params["tunnel_options"] = desired
    module = FakeModule(params, check_mode=True)
    client = Mock()
    with pytest.raises(ModuleFail, match=message):
        plugin.validate_inputs(module)
        plugin.ensure_present(client, module, connection)

    assert client.mock_calls == []


@pytest.fixture
def params(module_spec):
    return {name: deepcopy(spec.get("default")) for name, spec in module_spec["argument_spec"].items()} | {
        "name": "branch",
    }


def test_pending_vpn_with_allocated_endpoints_compares_in_check_mode(params, connection):
    connection["State"] = "pending"
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.2", "phase1_encryption_algorithms": ["AES128"]}]
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=True), connection)["changed"] is False
    assert client.mock_calls == []


def test_pending_vpn_waits_for_endpoints_before_real_update(params, connection):
    pending = deepcopy(connection)
    pending["State"] = "pending"
    pending["Options"]["TunnelOptions"] = []
    params["tunnel_options"] = [{"phase1_encryption_algorithms": ["AES256"]}]
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with patch.object(plugin, "wait_for_connection") as waiter:
        client.attach_mock(waiter, "wait_connection")
        assert ensure(client, FakeModule(params), pending)["changed"] is True

    assert [call[0] for call in client.mock_calls][:2] == ["wait_connection", "describe_vpn_connections"]
    assert [call.kwargs["VpnTunnelOutsideIpAddress"] for call in client.modify_vpn_tunnel_options.call_args_list] == [
        "203.0.113.1",
        "203.0.113.2",
    ]


def test_module_argument_defaults(module_spec):
    result = ArgumentSpecValidator(argument_spec=module_spec["argument_spec"]).validate({"name": "branch"})
    assert not result.error_messages
    expected = {
        "connection_type": "ipsec.1",
        "purge_routes": True,
        "purge_tags": True,
        "routes": None,
        "state": "present",
        "static_only": None,
        "tags": None,
        "tunnel_options": None,
        "wait_delay": 15,
        "wait_timeout": 600,
    }
    for name, default in expected.items():
        assert result.validated_parameters[name] == default

    assert "delay" in module_spec["argument_spec"]["wait_delay"]["aliases"]


@pytest.mark.parametrize("purge", [True, False])
def test_omitted_routes_are_preserved(params, connection, purge):
    params["purge_routes"] = purge
    client = Mock()
    assert ensure(client, FakeModule(params), connection)["changed"] is False
    client.delete_vpn_connection_route.assert_not_called()


def test_purge_routes_with_explicit_empty_routes_removes_existing_routes(params, connection):
    params.update(purge_routes=True, routes=[])
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with patch.object(plugin, "wait_for_route_deleted") as waiter:
        assert ensure(client, FakeModule(params), connection)["changed"]

    waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.0.0.0/8")
    client.delete_vpn_connection_route.assert_called_once_with(
        VpnConnectionId="vpn-123", DestinationCidrBlock="10.0.0.0/8", aws_retry=True
    )


def ensure(client, module, connection):
    with pytest.raises(ModuleExit) as result:
        plugin.ensure_present(client, module, connection)

    return result.value.values


def test_omitted_options_leave_existing_configuration_unchanged(params, connection):
    client = Mock()
    result = ensure(client, FakeModule(params), connection)
    assert result["changed"] is False
    assert client.mock_calls == []
    assert result["vpn_connection"]["tags"]["OwnerTeam"] == "NetworkOps"


def test_results_remove_generated_secrets_without_mutating_input(connection):
    original = deepcopy(connection)
    result = plugin.normalize_connection(connection)
    assert "SECRET" not in json.dumps(result)
    assert "customer_gateway_configuration" not in result
    assert connection == original


def test_results_allow_null_tunnel_options(connection):
    connection["Options"]["TunnelOptions"] = None
    result = plugin.normalize_connection(connection)
    assert result["options"]["tunnel_options"] is None
    assert "customer_gateway_configuration" not in result


def test_null_tags_are_normalized_and_compared(params, connection):
    connection["Tags"] = None
    assert plugin.normalize_connection(connection)["tags"] == {}
    assert plugin.desired_tags(FakeModule(params), connection) == ({"Name": "branch"}, [])


@pytest.mark.parametrize("check_mode", [True, False])
def test_shared_settings_update_both_discovered_tunnels(params, connection, check_mode):
    params["tunnel_options"] = [{"ike_versions": ["ikev2"]}]
    client = Mock()
    updated = deepcopy(connection)
    for tunnel in updated["Options"]["TunnelOptions"]:
        tunnel["IkeVersions"] = [{"Value": "ikev2"}]

    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    assert ensure(client, FakeModule(params, check_mode=check_mode), connection)["changed"]
    if check_mode:
        assert client.mock_calls == []
    else:
        assert client.modify_vpn_tunnel_options.call_count == 2
        assert {
            call.kwargs["VpnTunnelOutsideIpAddress"] for call in client.modify_vpn_tunnel_options.call_args_list
        } == {"203.0.113.1", "203.0.113.2"}

    client.reset_mock()
    updated["Options"]["TunnelOptions"].reverse()
    assert ensure(client, FakeModule(params, check_mode=check_mode), updated)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("actual", ["0EXAMPLE_LEGACY", "EXAMPLE-LEGACY-KEY"])
def test_returned_psk_comparison_does_not_apply_input_restrictions(params, connection, actual):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "pre_shared_key": "EXAMPLE_REPLACEMENT"}]
    connection["Options"]["TunnelOptions"][0]["PreSharedKey"] = actual
    assert plugin.tunnel_deltas(FakeModule(params), connection) == [
        ("203.0.113.1", {"PreSharedKey": "EXAMPLE_REPLACEMENT"})
    ]


def test_shared_settings_only_modify_tunnels_with_differences(params, connection):
    params["tunnel_options"] = [{"phase1_encryption_algorithms": ["AES128"]}]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == [
        ("203.0.113.1", {"Phase1EncryptionAlgorithms": [{"Value": "AES128"}]})
    ]


@pytest.mark.parametrize("existing", [True, False])
def test_shared_inside_cidr_is_rejected_before_mutation(params, connection, existing):
    params.update(
        customer_gateway_id="cgw-123",
        vpn_gateway_id="vgw-123",
        tunnel_options=[{"tunnel_inside_cidr": "169.254.10.0/30"}],
    )
    client = Mock()
    with pytest.raises(ModuleFail, match="CIDR"):
        plugin.ensure_present(client, FakeModule(params), connection if existing else None)

    assert client.mock_calls == []


@pytest.mark.parametrize("route", ["10.0.0.0/8'", "not-a-cidr", "10.0.0.1/8"])
def test_invalid_ec2_route_cidrs_fail_before_waiter_construction(params, connection, route):
    connection["Routes"][0]["DestinationCidrBlock"] = route
    assert plugin.validate_connection(FakeModule(params), connection) is connection

    with patch.object(plugin, "run_waiter") as run, pytest.raises(ModuleFail):
        plugin.wait_for_route_deleted(Mock(), FakeModule(params), "vpn-123", route)

    run.assert_not_called()


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize(
    "field, option, cidrs",
    [
        ("TunnelInsideCidr", "tunnel_inside_cidr", ["169.254.10.0/30", "169.254.11.0/30"]),
        ("TunnelInsideIpv6Cidr", "tunnel_inside_ipv6_cidr", ["fd00::/126", "fd00::4/126"]),
    ],
)
def test_inside_cidr_swap_fails_before_any_mutation(params, connection, check_mode, field, option, cidrs):
    if "Ipv6" in field:
        connection["Options"]["TunnelInsideIpVersion"] = "ipv6"
        connection["TransitGatewayId"] = "tgw-123"

    for tunnel, cidr in zip(connection["Options"]["TunnelOptions"], cidrs):
        tunnel[field] = cidr

    params["tunnel_options"] = [{option: cidrs[1]}, {option: cidrs[0]}]
    params["local_ipv4_network_cidr"] = "10.0.0.0/8"
    module = FakeModule(params, check_mode=check_mode)
    plugin.validate_inputs(module)
    client = Mock()
    with pytest.raises(ModuleFail, match="already assigned to another tunnel"):
        plugin.ensure_present(client, module, connection)

    assert client.mock_calls == []


@pytest.mark.parametrize("route", ["10.0.0.1/8", "fd00::/64", "invalid"])
def test_unmanaged_route_cidr_does_not_block_vpn_deletion(params, connection, route):
    connection["Routes"][0]["DestinationCidrBlock"] = route
    module = FakeModule(params)
    plugin.validate_connection(module, connection)
    client = Mock()
    assert ensure(client, module, connection)["changed"] is False
    with patch.object(plugin, "wait_for_connection"), pytest.raises(ModuleExit) as result:
        plugin.ensure_absent(client, module, connection)

    assert result.value.values["changed"] is True
    client.delete_vpn_connection.assert_called_once()


@pytest.mark.parametrize("cidr, changed", [("169.254.10.0/30", False), ("169.254.12.0/30", True)])
def test_inside_cidr_updates_allow_own_or_unused_cidr(params, connection, cidr, changed):
    connection["Options"]["TunnelOptions"][0]["TunnelInsideCidr"] = "169.254.10.0/30"
    connection["Options"]["TunnelOptions"][1]["TunnelInsideCidr"] = "169.254.11.0/30"
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "tunnel_inside_cidr": cidr}]
    assert bool(plugin.tunnel_deltas(FakeModule(params), connection)) is changed


@pytest.mark.parametrize("check_mode", [True, False])
def test_invalid_route_to_purge_fails_before_any_mutation(params, connection, check_mode):
    connection["Routes"][0]["DestinationCidrBlock"] = "invalid"
    params.update(routes=[], local_ipv4_network_cidr="10.0.0.0/8")
    client = Mock()
    with pytest.raises(ModuleFail, match="canonical IPv4 CIDR"):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert client.mock_calls == []


def test_reconcile_invalid_route_fails_before_sdk_call(params):
    client = Mock()
    with pytest.raises(ModuleFail, match="canonical IPv4 CIDR"):
        plugin.reconcile_routes(client, FakeModule(params), "vpn-123", set(), {"invalid"})

    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("selection", [{}, {"outside_ip_address": "203.0.113.1"}])
def test_null_tunnel_options_fail_cleanly_when_selected(params, connection, check_mode, selection):
    connection["Options"]["TunnelOptions"] = None
    params["tunnel_options"] = [dict(selection, phase1_encryption_algorithms=["AES256"])]
    client = Mock()
    message = "No unique tunnel" if selection else "EC2 did not return the requested tunnels"
    with pytest.raises(ModuleFail, match=message):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert client.mock_calls == []


def test_null_tunnel_options_without_selection_are_unchanged(params, connection):
    connection["Options"]["TunnelOptions"] = None
    client = Mock()
    assert ensure(client, FakeModule(params), connection)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("name", [None, "branch"])
def test_desired_tags_normalize_a_copy(params, name):
    tags = {123: 456}
    params.update(name=name, tags=tags)
    module = FakeModule(params)
    with patch.object(plugin, "require_valid_tags", wraps=plugin.require_valid_tags) as validate:
        plugin.validate_inputs(module)
        desired, removed = plugin.desired_tags(module, {})

    assert desired == ({"123": "456", "Name": "branch"} if name else {"123": "456"})
    assert removed == []
    assert params["tags"] is tags
    assert tags == {123: 456}
    validate.assert_called_once()


def test_desired_tags_validate_including_name(params):
    params["tags"] = {f"key-{index}": "value" for index in range(50)}
    with pytest.raises(ModuleFail, match="at most 50"):
        plugin.desired_tags(FakeModule(params), {})


def test_algorithms_compare_as_sets_and_ignore_omitted_fields(params, connection):
    params["tunnel_options"] = [
        {"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256", "AES128", "AES128"]}
    ]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == []


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("versions", [["ikev2"], ["ikev1", "ikev2"]])
def test_ike_versions_use_sdk_response_casing_and_are_idempotent(params, connection, check_mode, versions):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "ike_versions": versions}]
    tunnel = connection["Options"]["TunnelOptions"][0]
    tunnel["IkeVersions"] = [{"Value": value} for value in reversed(versions)]
    validate_parameters(tunnel, Session().get_service_model("ec2").shape_for("TunnelOption"))
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), connection)["changed"] is False
    assert client.mock_calls == []


def test_ike_versions_update_uses_sdk_request_casing(params, connection):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "ike_versions": ["ikev2"]}]
    connection["Options"]["TunnelOptions"][0]["IkeVersions"] = [{"Value": "ikev1"}]
    client = Mock()
    updated = deepcopy(connection)
    updated["Options"]["TunnelOptions"][0]["IkeVersions"] = [{"Value": "ikev2"}]
    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    assert ensure(client, FakeModule(params), connection)["changed"]
    client.modify_vpn_tunnel_options.assert_called_once_with(
        VpnConnectionId="vpn-123",
        VpnTunnelOutsideIpAddress="203.0.113.1",
        TunnelOptions={"IKEVersions": [{"Value": "ikev2"}]},
        aws_retry=True,
    )
    request = dict(client.modify_vpn_tunnel_options.call_args.kwargs)
    request.pop("aws_retry")
    validate_parameters(
        request, Session().get_service_model("ec2").operation_model("ModifyVpnTunnelOptions").input_shape
    )
    client.reset_mock()
    assert ensure(client, FakeModule(params), updated)["changed"] is False
    assert client.mock_calls == []


def test_outside_ip_selection_survives_response_reordering(params, connection):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.2", "phase1_encryption_algorithms": ["AES256"]}]
    expected = [("203.0.113.2", {"Phase1EncryptionAlgorithms": [{"Value": "AES256"}]})]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == expected
    connection["Options"]["TunnelOptions"].reverse()
    assert plugin.tunnel_deltas(FakeModule(params), connection) == expected


@pytest.mark.parametrize(
    "tunnels",
    [
        [{"outside_ip_address": "203.0.113.99"}],
        [{"outside_ip_address": "203.0.113.2"}, {"outside_ip_address": "203.0.113.2"}],
        [{"outside_ip_address": "203.0.113.2"}, {"phase1_encryption_algorithms": ["AES256"]}],
    ],
)
def test_invalid_or_overlapping_tunnel_selection_fails(params, connection, tunnels):
    params["tunnel_options"] = tunnels
    with pytest.raises(ModuleFail):
        plugin.tunnel_deltas(FakeModule(params), connection)


@pytest.mark.parametrize("reverse", [True, False])
@pytest.mark.parametrize("check_mode", [True, False])
def test_mixed_tunnel_selection_rejected_in_either_order(params, connection, reverse, check_mode):
    tunnels = [{"outside_ip_address": "203.0.113.2", "ike_versions": ["ikev2"]}, {"ike_versions": ["ikev2"]}]
    params["tunnel_options"] = list(reversed(tunnels)) if reverse else tunnels
    client = Mock()
    with pytest.raises(ModuleFail, match="Do not mix tunnel entries"):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert client.mock_calls == []


@pytest.mark.parametrize("actual", ["EXAMPLE_REPLACEMENT", "EXAMPLE_DIFFERENT", "EXAMPLE_é"])
def test_psk_uses_constant_time_comparison(params, connection, actual):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "pre_shared_key": "EXAMPLE_REPLACEMENT"}]
    connection["Options"]["TunnelOptions"][0]["PreSharedKey"] = actual
    with patch.object(plugin.secrets, "compare_digest", wraps=plugin.secrets.compare_digest) as compare:
        changes = plugin.tunnel_deltas(FakeModule(params), connection)

    compare.assert_called_once_with(b"EXAMPLE_REPLACEMENT", actual.encode("utf-8"))
    assert bool(changes) == (actual != "EXAMPLE_REPLACEMENT")


def test_encryption_update_waits_between_tunnels_and_rereads(params, connection):
    params["tunnel_options"] = [
        {"outside_ip_address": address, "phase1_encryption_algorithms": ["AES256"]}
        for address in ("203.0.113.1", "203.0.113.2")
    ]
    client = Mock()
    updated = deepcopy(connection)
    for tunnel in updated["Options"]["TunnelOptions"]:
        tunnel["Phase1EncryptionAlgorithms"] = [{"Value": "AES256"}]

    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    result = ensure(client, FakeModule(params), connection)
    assert result["changed"]
    assert [call[0] for call in client.mock_calls] == [
        "modify_vpn_tunnel_options",
        "get_waiter",
        "get_waiter().wait",
        "modify_vpn_tunnel_options",
        "get_waiter",
        "get_waiter().wait",
        "describe_vpn_connections",
    ]
    for call, address in zip(client.modify_vpn_tunnel_options.call_args_list, ["203.0.113.1", "203.0.113.2"]):
        assert call.kwargs == {
            "VpnConnectionId": "vpn-123",
            "VpnTunnelOutsideIpAddress": address,
            "TunnelOptions": {"Phase1EncryptionAlgorithms": [{"Value": "AES256"}]},
            "aws_retry": True,
        }
        request = {key: value for key, value in call.kwargs.items() if key != "aws_retry"}
        shape = Session().get_service_model("ec2").operation_model("ModifyVpnTunnelOptions").input_shape
        validate_parameters(request, shape)

    assert ensure(Mock(), FakeModule(params), updated)["changed"] is False


def test_check_mode_predicts_all_changes_without_mutation(params, connection):
    params.update(
        tunnel_options=[{"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256"]}],
        tags={},
        routes=[],
        local_ipv4_network_cidr="10.0.0.0/8",
    )
    client = Mock()
    result = ensure(client, FakeModule(params, check_mode=True), connection)
    assert result["changed"]
    assert client.mock_calls == []
    assert result["vpn_connection"] == plugin.normalize_connection(connection)


def test_connection_cidr_uses_correct_api(params, connection):
    params["local_ipv4_network_cidr"] = "10.0.0.0/8"
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    assert ensure(client, FakeModule(params), connection)["changed"]
    client.modify_vpn_connection_options.assert_called_once_with(
        VpnConnectionId="vpn-123", LocalIpv4NetworkCidr="10.0.0.0/8", aws_retry=True
    )
    client.modify_vpn_tunnel_options.assert_not_called()


@pytest.mark.parametrize("purge,removes", [(True, True), (False, False)])
def test_explicit_empty_routes_and_tags(params, connection, purge, removes):
    params.update(routes=[], tags={}, purge_routes=purge, purge_tags=purge)
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with patch.object(plugin, "wait_for_route_deleted") as waiter:
        result = ensure(client, FakeModule(params), connection)

    assert bool(waiter.call_count) == removes
    assert result["changed"] == removes
    assert bool(client.delete_vpn_connection_route.call_count) == removes
    assert bool(client.delete_tags.call_count) == removes
    if removes:
        assert client.delete_tags.call_args.kwargs["Tags"] == [{"Key": "OwnerTeam"}]


@pytest.mark.parametrize(
    "field,value", [("static_only", False), ("vpn_gateway_id", "vgw-other"), ("customer_gateway_id", "cgw-other")]
)
def test_immutable_changes_fail_before_mutation(params, connection, field, value):
    params[field] = value
    client = Mock()
    with pytest.raises(ModuleFail, match=f"Cannot change {field}"):
        plugin.ensure_present(client, FakeModule(params), connection)

    assert client.mock_calls == []


def test_creation_tags_atomically_and_adds_routes(params, connection):
    params.update(
        customer_gateway_id="cgw-123",
        vpn_gateway_id="vgw-123",
        static_only=True,
        routes=["10.20.0.0/16"],
        tunnel_options=[{"ike_versions": ["ikev2"]}],
    )
    created = deepcopy(connection)
    created["Routes"] = []
    created["Options"]["TunnelOptions"][0]["IkeVersions"] = [{"Value": "ikev2"}]
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": created}
    client.describe_vpn_connections.return_value = {"VpnConnections": [created]}
    with patch.object(plugin, "wait_for_route_available") as waiter:
        assert ensure(client, FakeModule(params), None)["changed"]

    waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.20.0.0/16")
    request = dict(client.create_vpn_connection.call_args.kwargs)
    assert request.pop("aws_retry") is True
    assert request["TagSpecifications"] == [
        {"ResourceType": "vpn-connection", "Tags": [{"Key": "Name", "Value": "branch"}]}
    ]
    assert "LocalIpv4NetworkCidr" not in request["Options"]
    assert request["Options"]["TunnelOptions"] == [{"IKEVersions": [{"Value": "ikev2"}]}] * 2
    first, second = request["Options"]["TunnelOptions"]
    assert first is not second
    assert first["IKEVersions"] is not second["IKEVersions"]
    validate_parameters(request, Session().get_service_model("ec2").operation_model("CreateVpnConnection").input_shape)
    client.create_vpn_connection_route.assert_called_once_with(
        VpnConnectionId="vpn-123", DestinationCidrBlock="10.20.0.0/16", aws_retry=True
    )


def test_create_check_mode_validates_and_does_not_invent_an_id(params):
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123")
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=True), None) == {"changed": True, "vpn_connection": {}}
    assert client.mock_calls == []
    params["customer_gateway_id"] = None
    with pytest.raises(ModuleFail):
        plugin.ensure_present(client, FakeModule(params, check_mode=True), None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"wait_delay": 0},
        {"wait_timeout": 0},
        {"name": ""},
        {"filters": {}},
        {"routes": ["10.0.0.1/8"]},
        {"local_ipv4_network_cidr": "::/0"},
        {"tunnel_options": [{}, {}, {}]},
        {"tunnel_options": [{"ike_versions": []}]},
        {"tunnel_options": [{"pre_shared_key": "0EXAMPLE_SECRET"}]},
        {"tunnel_options": [{"tunnel_inside_cidr": "169.254.0.0/30"}]},
        {"tunnel_options": [{"tunnel_inside_cidr": "169.254.10.0/29"}]},
        {"tunnel_options": [{"tunnel_inside_cidr": "169.254.10.0/30"}] * 2},
        {"tags": {"Name": "different"}},
    ],
)
def test_invalid_inputs_fail_locally(params, overrides):
    params.update(overrides)
    with pytest.raises(ModuleFail):
        plugin.validate_inputs(FakeModule(params))


@pytest.mark.parametrize("state,changed", [("available", True), ("deleting", False)])
def test_delete_is_idempotent_and_waits(params, connection, state, changed):
    connection["State"] = state
    client = Mock()
    with pytest.raises(ModuleExit) as result:
        plugin.ensure_absent(client, FakeModule(params), connection)

    assert result.value.values == {"changed": changed, "vpn_connection": {}}
    assert bool(client.delete_vpn_connection.call_count) == changed
    client.get_waiter.assert_called_once_with("vpn_connection_deleted")


def test_absent_check_mode_and_already_absent(params, connection):
    client = Mock()
    with pytest.raises(ModuleExit) as result:
        plugin.ensure_absent(client, FakeModule(params, check_mode=True), connection)

    assert result.value.values["changed"]
    with pytest.raises(ModuleExit) as result:
        plugin.ensure_absent(client, FakeModule(params), None)

    assert result.value.values == {"changed": False, "vpn_connection": {}}
    assert client.mock_calls == []


def test_deleting_connection_is_never_recreated(params, connection):
    connection["State"] = "deleting"
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    found = plugin.find_connection(client, FakeModule(params))
    with pytest.raises(ModuleFail, match="is deleting"):
        plugin.ensure_present(client, FakeModule(params), found)

    client.create_vpn_connection.assert_not_called()


@pytest.mark.parametrize(
    "response", [{}, {"VpnConnections": None}, {"VpnConnections": [None]}, {"VpnConnections": [{}]}]
)
def test_invalid_describe_response_fails(params, response):
    client = Mock()
    client.describe_vpn_connections.return_value = response
    with pytest.raises(ModuleFail):
        plugin.find_connection(client, FakeModule(params))


def test_ambiguous_selection_fails(params, connection):
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection, connection]}
    with pytest.raises(ModuleFail, match="Multiple VPN connections"):
        plugin.find_connection(client, FakeModule(params))


@pytest.mark.parametrize("with_active", [True, False])
def test_deleted_connections_do_not_require_options(params, connection, with_active):
    client = Mock()
    client.describe_vpn_connections.return_value = {
        "VpnConnections": [{"VpnConnectionId": "vpn-old", "State": "deleted"}] + ([connection] if with_active else [])
    }
    found = plugin.find_connection(client, FakeModule(params))
    assert found == (connection if with_active else None)
    if not with_active:
        with pytest.raises(ModuleExit) as result:
            plugin.ensure_absent(client, FakeModule(params), found)

        assert result.value.values == {"changed": False, "vpn_connection": {}}
        client.delete_vpn_connection.assert_not_called()


def test_missing_existing_address_family_cannot_match_requested_ipv6(params, connection):
    connection["Options"].pop("TunnelInsideIpVersion")
    connection["TransitGatewayId"] = "tgw-123"
    connection.pop("VpnGatewayId")
    params["tunnel_inside_ip_version"] = "ipv6"
    client = Mock()
    with pytest.raises(ModuleFail, match="Cannot change tunnel_inside_ip_version"):
        plugin.ensure_present(client, FakeModule(params), connection)

    assert client.mock_calls == []
    params["tunnel_inside_ip_version"] = "ipv4"
    assert ensure(client, FakeModule(params), connection)["changed"] is False


@pytest.mark.parametrize("static_only", [False, True])
@pytest.mark.parametrize("missing", [True, False])
@pytest.mark.parametrize("check_mode", [True, False])
def test_missing_or_null_existing_routing_mode_defaults_to_dynamic(
    params, connection, static_only, missing, check_mode
):
    connection["Options"].pop("StaticRoutesOnly")
    if not missing:
        connection["Options"]["StaticRoutesOnly"] = None

    params["static_only"] = static_only
    module = FakeModule(params, check_mode=check_mode)
    client = Mock()
    if static_only:
        with pytest.raises(ModuleFail, match="Cannot change static_only"):
            plugin.ensure_present(client, module, connection)
    else:
        assert ensure(client, module, connection)["changed"] is False

    assert client.mock_calls == []


@pytest.mark.parametrize("routes", [None, {}, [None], [{}], [{"DestinationCidrBlock": ""}]])
def test_invalid_route_responses_fail_cleanly(params, connection, routes):
    connection["Routes"] = routes
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with pytest.raises(ModuleFail, match="invalid VPN connection routes"):
        plugin.find_connection(client, FakeModule(params))


@pytest.mark.parametrize("tunnels", [{}, [None], ["invalid"]])
def test_invalid_tunnel_responses_fail_cleanly(params, connection, tunnels):
    connection["Options"]["TunnelOptions"] = tunnels
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with pytest.raises(ModuleFail, match="invalid VPN connection tunnel options"):
        plugin.find_connection(client, FakeModule(params))


@pytest.mark.parametrize("timeout", [True, False])
def test_route_removal_waits_before_returning_final_state(params, connection, timeout):
    params["routes"] = []
    client = Mock()
    final = deepcopy(connection)
    final["Routes"] = []
    client.describe_vpn_connections.return_value = {"VpnConnections": [final]}
    with patch.object(plugin, "wait_for_route_deleted") as waiter:
        client.attach_mock(waiter, "wait_route")
        if timeout:
            waiter.side_effect = ModuleFail({"msg": "Timeout"})
            with pytest.raises(ModuleFail, match="Timeout"):
                plugin.ensure_present(client, FakeModule(params), connection)
        else:
            result = ensure(client, FakeModule(params), connection)
            assert result["changed"]
            assert result["vpn_connection"]["routes"] == []

    assert [call[0] for call in client.mock_calls] == ["delete_vpn_connection_route", "wait_route"] + (
        [] if timeout else ["describe_vpn_connections"]
    )


def test_ipv6_creation_uses_requested_family(params):
    params.update(transit_gateway_id="tgw-123", tunnel_inside_ip_version="ipv6")
    plugin.validate_configuration(FakeModule(params))


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("existing", [True, False])
def test_ipv4_tunnel_cidr_rejected_on_ipv6_connection(params, connection, check_mode, existing):
    params.update(
        customer_gateway_id="cgw-123",
        transit_gateway_id="tgw-123",
        tunnel_options=[{"tunnel_inside_cidr": "169.254.10.0/30"}],
    )
    if existing:
        connection.pop("VpnGatewayId")
        connection["TransitGatewayId"] = "tgw-123"
        connection["Options"]["TunnelInsideIpVersion"] = "ipv6"
    else:
        params["tunnel_inside_ip_version"] = "ipv6"

    client = Mock()
    module = FakeModule(params, check_mode=check_mode)
    plugin.validate_inputs(module)
    with pytest.raises(ModuleFail, match="tunnel_inside_cidr requires tunnel_inside_ip_version=ipv4"):
        plugin.ensure_present(client, module, connection if existing else None)

    assert client.mock_calls == []


@pytest.mark.parametrize(
    "family,option,cidr",
    [("ipv4", "tunnel_inside_cidr", "169.254.10.0/30"), ("ipv6", "tunnel_inside_ipv6_cidr", "fd00::/126")],
)
def test_matching_tunnel_cidr_family_is_valid(params, family, option, cidr):
    params.update(transit_gateway_id="tgw-123", tunnel_inside_ip_version=family, tunnel_options=[{option: cidr}])
    module = FakeModule(params)
    plugin.validate_inputs(module)
    plugin.validate_configuration(module)


@pytest.mark.parametrize("check_mode", [True, False])
def test_requested_deleting_route_is_recreated_after_deletion(params, connection, check_mode):
    params["routes"] = ["10.0.0.0/8"]
    connection["Routes"][0]["State"] = "deleting"
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with (
        patch.object(plugin, "wait_for_route_deleted") as waiter,
        patch.object(plugin, "wait_for_route_available") as available,
    ):
        client.attach_mock(waiter, "wait_route")
        client.attach_mock(available, "wait_available")
        assert ensure(client, FakeModule(params, check_mode=check_mode), connection)["changed"]

    if check_mode:
        assert client.mock_calls == []
    else:
        assert [call[0] for call in client.mock_calls] == [
            "wait_route",
            "create_vpn_connection_route",
            "wait_available",
            "describe_vpn_connections",
        ]
        waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.0.0.0/8")
        client.create_vpn_connection_route.assert_called_once_with(
            VpnConnectionId="vpn-123", DestinationCidrBlock="10.0.0.0/8", aws_retry=True
        )


def test_route_deletion_timeout_prevents_recreation(params, connection):
    params["routes"] = ["10.0.0.0/8"]
    connection["Routes"][0]["State"] = "deleting"
    client = Mock()
    with (
        patch.object(plugin, "wait_for_route_deleted", side_effect=ModuleFail({"msg": "Timeout"})),
        pytest.raises(ModuleFail, match="Timeout"),
    ):
        plugin.ensure_present(client, FakeModule(params), connection)

    assert client.mock_calls == []


@pytest.mark.parametrize("final_state", ["deleted", "missing", "deleting"])
def test_route_waiter_matches_only_the_requested_route(params, final_state):
    params.update(wait_timeout=1, wait_delay=1)
    client = Session().create_client(
        "ec2", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    pending = {"DestinationCidrBlock": "10.0.0.0/8", "State": "deleting"}
    unrelated = {"DestinationCidrBlock": "192.168.0.0/16", "State": "available"}
    final_routes = [unrelated] + ([] if final_state == "missing" else [dict(pending, State=final_state)])
    describe = Mock(
        side_effect=[
            {"VpnConnections": [{"Routes": [pending, unrelated]}]},
            {"VpnConnections": [{"Routes": final_routes}]},
        ]
    )
    with patch.object(client, "describe_vpn_connections", describe), patch("botocore.waiter.time.sleep"):
        if final_state == "deleting":
            with pytest.raises(ModuleFail, match="Unable to wait for route"):
                plugin.wait_for_route_deleted(client, FakeModule(params), "vpn-123", "10.0.0.0/8")
        else:
            plugin.wait_for_route_deleted(client, FakeModule(params), "vpn-123", "10.0.0.0/8")

    assert describe.call_count == 2
    assert all(call.kwargs == {"VpnConnectionIds": ["vpn-123"]} for call in describe.call_args_list)


@pytest.mark.parametrize("actual", [None, "", "********", "<redacted>"])
@pytest.mark.parametrize("check_mode", [True, False])
def test_unavailable_psk_fails_before_any_mutation(params, connection, actual, check_mode):
    params.update(
        tunnel_options=[{"outside_ip_address": "203.0.113.1", "pre_shared_key": "EXAMPLE_DESIRED_SECRET"}],
        local_ipv4_network_cidr="10.20.0.0/16",
        tags={},
    )
    tunnel = connection["Options"]["TunnelOptions"][0]
    if actual is None:
        tunnel.pop("PreSharedKey")
    else:
        tunnel["PreSharedKey"] = actual

    client = Mock()
    with pytest.raises(ModuleFail, match="Cannot compare pre_shared_key") as result:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert "EXAMPLE_DESIRED_SECRET" not in str(result.value)
    assert client.mock_calls == []
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256"]}]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == [
        ("203.0.113.1", {"Phase1EncryptionAlgorithms": [{"Value": "AES256"}]})
    ]


def test_visible_psk_can_be_compared_and_changed(params, connection):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "pre_shared_key": "EXAMPLE_GENERATED_SECRET"}]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == []
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "pre_shared_key": "EXAMPLE_REPLACEMENT_SECRET"}]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == [
        ("203.0.113.1", {"PreSharedKey": "EXAMPLE_REPLACEMENT_SECRET"})
    ]


def test_sdk_errors_report_operations_and_resource(params, connection):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256"]}]
    client = Mock()
    client.modify_vpn_tunnel_options.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "Denied"}}, "ModifyVpnTunnelOptions"
    )
    with pytest.raises(ModuleFail, match="vpn-123 tunnel 203.0.113.1"):
        plugin.ensure_present(client, FakeModule(params), connection)

    client.get_waiter.assert_not_called()
    client.get_waiter.return_value.wait.side_effect = WaiterError(name="VPN", reason="Timeout", last_response={})
    with pytest.raises(ModuleFail, match="vpn-123 to become available"):
        plugin.wait_for_connection(client, FakeModule(params), "vpn-123")


@pytest.mark.parametrize(
    "arguments,message",
    [
        ({"name": "branch", "wait_delay": 0}, "wait_delay must be 1 or greater"),
        ({"name": "branch", "tunnel_options": [{"phase1_encryption_algorithms": []}]}, "must not be empty"),
        ({"name": "branch", "vpn_connection_id": "vpn-123"}, "mutually exclusive"),
    ],
)
def test_real_ansible_argument_validation(module_spec, arguments, message):
    spec = {key: value for key, value in module_spec.items() if key != "supports_check_mode"}
    result = ArgumentSpecValidator(**spec).validate(arguments)
    if result.error_messages:
        assert message in "; ".join(result.error_messages)
    else:
        with pytest.raises(ModuleFail, match=message):
            plugin.validate_inputs(FakeModule(result.validated_parameters))


@pytest.mark.parametrize("addresses", [("203.0.113.1", "203.0.113.2"), ("203.0.113.9", "203.0.113.10")])
def test_explicit_tunnel_selection_is_stable(params, connection, addresses):
    for tunnel, address in zip(connection["Options"]["TunnelOptions"], addresses):
        tunnel["OutsideIpAddress"] = address

    params["tunnel_options"] = [{"outside_ip_address": addresses[0], "phase1_encryption_algorithms": ["AES256"]}]
    expected = [(addresses[0], {"Phase1EncryptionAlgorithms": [{"Value": "AES256"}]})]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == expected
    connection["Options"]["TunnelOptions"].reverse()
    assert plugin.tunnel_deltas(FakeModule(params), connection) == expected


@pytest.mark.parametrize("address", [None, "not-an-ip"])
def test_invalid_tunnel_outside_ip_fails_cleanly(params, connection, address):
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256"]}]
    connection["Options"]["TunnelOptions"][0]["OutsideIpAddress"] = address
    with pytest.raises(ModuleFail, match="outside IP"):
        plugin.tunnel_deltas(FakeModule(params), connection)


def test_creation_does_not_reapply_asymmetric_tunnels_or_reread_twice(params, connection):
    params.update(
        customer_gateway_id="cgw-123",
        vpn_gateway_id="vgw-123",
        tunnel_options=[
            {"phase1_encryption_algorithms": ["AES128", "AES256"]},
            {"phase1_encryption_algorithms": ["AES128"]},
        ],
    )
    connection["Options"]["TunnelOptions"].reverse()
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": connection}
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    assert ensure(client, FakeModule(params), None)["changed"]
    client.modify_vpn_tunnel_options.assert_not_called()
    client.describe_vpn_connections.assert_called_once()


@pytest.mark.parametrize("reverse_response", [True, False])
def test_asymmetric_tunnels_converge_after_creation_order_differs(params, connection, reverse_response):
    params.update(
        customer_gateway_id="cgw-123",
        vpn_gateway_id="vgw-123",
        tunnel_options=[{"phase1_encryption_algorithms": ["AES256"]}, {"phase1_encryption_algorithms": ["AES128"]}],
    )
    current = deepcopy(connection)
    # Simulate EC2 assigning the higher outside IP to the first creation entry.
    current["Options"]["TunnelOptions"][0]["Phase1EncryptionAlgorithms"] = [{"Value": "AES128"}]
    current["Options"]["TunnelOptions"][1]["Phase1EncryptionAlgorithms"] = [{"Value": "AES256"}]
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": current}
    client.describe_vpn_connections.return_value = {"VpnConnections": [current]}
    assert ensure(client, FakeModule(params), None)["changed"]

    def modify(**request):
        tunnel = next(
            t
            for t in current["Options"]["TunnelOptions"]
            if t["OutsideIpAddress"] == request["VpnTunnelOutsideIpAddress"]
        )
        tunnel.update(deepcopy(request["TunnelOptions"]))
        return {"VpnConnection": current}

    client.reset_mock()
    client.modify_vpn_tunnel_options.side_effect = modify
    if reverse_response:
        current["Options"]["TunnelOptions"].reverse()

    assert ensure(client, FakeModule(params), current)["changed"]
    assert client.modify_vpn_tunnel_options.call_count == 2
    current["Options"]["TunnelOptions"].reverse()
    client.reset_mock()
    assert ensure(client, FakeModule(params), current)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("actual", [[{}], [None], [{"Value": []}], {"Value": "AES256"}, ["AES256"], [{"Value": 1}]])
@pytest.mark.parametrize("check_mode", [True, False])
def test_malformed_algorithm_values_fail_before_mutation(params, connection, actual, check_mode):
    params["tunnel_options"] = [{"phase1_encryption_algorithms": ["AES256"]}]
    connection["Options"]["TunnelOptions"][1]["Phase1EncryptionAlgorithms"] = actual
    client = Mock()
    with pytest.raises(ModuleFail, match="EC2 returned invalid Phase1EncryptionAlgorithms"):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert client.mock_calls == []


@pytest.mark.parametrize("final_state", ["available", "pending", "missing"])
def test_route_availability_waiter_requires_requested_route(params, final_state):
    params.update(wait_delay=1, wait_timeout=1)
    client = Session().create_client(
        "ec2", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    route = {"DestinationCidrBlock": "10.0.0.0/8", "State": "pending"}
    unrelated = {"DestinationCidrBlock": "192.168.0.0/16", "State": "available"}
    final = [unrelated] + ([] if final_state == "missing" else [dict(route, State=final_state)])
    describe = Mock(
        side_effect=[{"VpnConnections": [{"Routes": [route, unrelated]}]}, {"VpnConnections": [{"Routes": final}]}]
    )
    with patch.object(client, "describe_vpn_connections", describe), patch("botocore.waiter.time.sleep"):
        if final_state == "available":
            plugin.wait_for_route_available(client, FakeModule(params), "vpn-123", "10.0.0.0/8")
        else:
            with pytest.raises(ModuleFail, match="to become available"):
                plugin.wait_for_route_available(client, FakeModule(params), "vpn-123", "10.0.0.0/8")

    assert describe.call_count == 2


@pytest.mark.parametrize("timeout", [True, False])
def test_added_routes_wait_before_final_read(params, connection, timeout):
    params["routes"] = ["10.0.0.0/8", "192.168.0.0/16"]
    updated = deepcopy(connection)
    updated["Routes"].append({"DestinationCidrBlock": "192.168.0.0/16", "State": "available"})
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    with patch.object(plugin, "wait_for_route_available") as waiter:
        client.attach_mock(waiter, "wait_available")
        if timeout:
            waiter.side_effect = ModuleFail({"msg": "Timeout"})
            with pytest.raises(ModuleFail, match="Timeout"):
                plugin.ensure_present(client, FakeModule(params), connection)
        else:
            result = ensure(client, FakeModule(params), connection)
            assert result["vpn_connection"]["routes"][-1]["state"] == "available"

    assert [call[0] for call in client.mock_calls] == ["create_vpn_connection_route", "wait_available"] + (
        [] if timeout else ["describe_vpn_connections"]
    )


@pytest.mark.parametrize("check_mode", [True, False])
def test_requested_pending_route_waits_without_recreation(params, connection, check_mode):
    params["routes"] = ["10.0.0.0/8"]
    connection["Routes"][0]["State"] = "pending"
    final = deepcopy(connection)
    final["Routes"][0]["State"] = "available"
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [final]}
    with patch.object(plugin, "wait_for_route_available") as waiter:
        result = ensure(client, FakeModule(params, check_mode=check_mode), connection)

    assert result["changed"] is False
    client.create_vpn_connection_route.assert_not_called()
    if check_mode:
        waiter.assert_not_called()
        assert client.mock_calls == []
    else:
        waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.0.0.0/8")
        assert result["vpn_connection"]["routes"][0]["state"] == "available"


@pytest.mark.parametrize("state,changed", [("available", True), ("deleting", False)])
def test_absent_check_mode_returns_empty_connection(params, connection, state, changed):
    connection["State"] = state
    client = Mock()
    with pytest.raises(ModuleExit) as result:
        plugin.ensure_absent(client, FakeModule(params, check_mode=True), connection)

    assert result.value.values == {"changed": changed, "vpn_connection": {}}
    assert client.mock_calls == []


@pytest.mark.parametrize("error_code,retried", [("IncorrectState", True), ("UnauthorizedOperation", False)])
def test_client_retries_transient_state_errors_only(params, connection, error_code, retried):
    module = FakeModule(params)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "find_connection", return_value=connection),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    retry = module.client.call_args.kwargs["retry_decorator"]
    raw_client = Mock()
    error = ClientError({"Error": {"Code": error_code, "Message": "EXAMPLE"}}, "ModifyVpnTunnelOptions")
    raw_client.modify_vpn_tunnel_options.side_effect = [error, {}]
    client = RetryingBotoClientWrapper(raw_client, retry)
    with patch("ansible_collections.amazon.aws.plugins.module_utils.cloud.time.sleep"):
        if retried:
            assert client.modify_vpn_tunnel_options(aws_retry=True) == {}
        else:
            with pytest.raises(ClientError):
                client.modify_vpn_tunnel_options(aws_retry=True)

    assert raw_client.modify_vpn_tunnel_options.call_count == (2 if retried else 1)
