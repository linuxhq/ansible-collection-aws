# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
from copy import deepcopy
from unittest.mock import ANY, Mock, patch

import pytest
from botocore.exceptions import ClientError, WaiterError
from botocore.session import Session
from botocore.validate import validate_parameters

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

from ansible_collections.amazon.aws.plugins.module_utils.retries import RetryingBotoClientWrapper

from ansible_collections.linuxhq.aws.plugins.module_utils import sdk
from ansible_collections.linuxhq.aws.plugins.modules import ec2_vpc_vpn as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_documents_shape,
    documented_returns,
)


@pytest.fixture(autouse=True)
def sdk_checks():
    with patch.object(plugin, "require_client_methods") as require:
        yield require


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
        "enable_acceleration": None,
        "outside_ip_address_type": None,
        "purge_routes": True,
        "purge_tags": True,
        "routes": None,
        "skip_tunnel_replacement": None,
        "state": "present",
        "pre_shared_key_storage": None,
        "static_only": None,
        "tags": None,
        "transport_transit_gateway_attachment_id": None,
        "tunnel_bandwidth": None,
        "tunnel_options": None,
        "vpn_concentrator_id": None,
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

    waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.0.0.0/8", changed=True)
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
    with patch.object(plugin, "wait_for_connection_deleted"), pytest.raises(ModuleExit) as result:
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
    assert validate.call_count == 2


def test_tags_validate_including_name_before_any_aws_call(params):
    params["tags"] = {f"key-{index}": "value" for index in range(50)}
    with pytest.raises(ModuleFail, match="at most 50"):
        plugin.validate_inputs(FakeModule(params))

    params["tags"] = {f"key-{index}": "value" for index in range(49)}
    plugin.validate_inputs(FakeModule(params))


def test_tag_keys_may_contain_128_characters_but_not_129(params):
    params["tags"] = {"k" * 128: "v"}
    plugin.validate_inputs(FakeModule(params))

    params["tags"] = {"k" * 129: "v"}
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_inputs(FakeModule(params))

    assert raised.value.values["msg"] == "tag keys must contain 1 to 128 characters and values at most 256 characters"


@pytest.mark.parametrize("key", [" ", "\t", "\N{IDEOGRAPHIC SPACE}"])
def test_blank_tag_keys_fail_before_any_aws_call(params, key):
    # Live: EC2 CreateTags rejects them (InvalidParameterValue), after any option, tunnel, or route change.
    params["tags"] = {key: "x"}
    client = Mock()
    module = FakeModule(params, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(module, "client") as connect,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": "tag keys must not be blank"}
    connect.assert_not_called()
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
def test_blank_tag_values_match_the_empty_value_ec2_stores(params, connection, check_mode):
    # Live: EC2 stores a tag value made only of spaces, tabs, and line breaks as "", and padded values as sent.
    connection["Tags"].extend([{"Key": "Blank", "Value": ""}, {"Key": "Pad", "Value": " x "}])
    params.update(tags={"Blank": " \t", "OwnerTeam": "NetworkOps", "Pad": " x "})
    client = Mock()
    result = ensure(client, FakeModule(params, check_mode=check_mode), connection)
    assert result["changed"] is False
    assert result["vpn_connection"]["tags"]["Blank"] == ""
    assert client.mock_calls == []


def test_creation_sends_blank_tag_values_as_ec2_stores_them(params, connection):
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123", tags={"Blank": " ", "Pad": "x "})
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": connection}
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with patch.object(plugin, "wait_for_connection"):
        ensure(client, FakeModule(params), None)

    (specification,) = client.create_vpn_connection.call_args.kwargs["TagSpecifications"]
    assert specification["ResourceType"] == "vpn-connection"
    assert sorted(specification["Tags"], key=lambda tag: tag["Key"]) == [
        {"Key": "Blank", "Value": ""},
        {"Key": "Name", "Value": "branch"},
        {"Key": "Pad", "Value": "x "},
    ]


def test_algorithms_compare_as_sets_and_ignore_omitted_fields(params, connection):
    params["tunnel_options"] = [
        {"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256", "AES128", "AES128"]}
    ]
    assert plugin.tunnel_deltas(FakeModule(params), connection) == []


DEFAULT_TUNNEL_LISTS = {
    "ike_versions": ["ikev2", "ikev1"],
    "phase1_encryption_algorithms": ["AES256-GCM-16", "AES128-GCM-16", "AES256", "AES128"],
    "phase2_encryption_algorithms": ["AES256-GCM-16", "AES128-GCM-16", "AES256", "AES128"],
    "phase1_integrity_algorithms": ["SHA2-512", "SHA2-384", "SHA2-256", "SHA1"],
    "phase2_integrity_algorithms": ["SHA2-512", "SHA2-384", "SHA2-256", "SHA1"],
    "phase1_dh_group_numbers": [24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 2],
    "phase2_dh_group_numbers": [24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 5, 2],
}


@pytest.fixture
def default_tunnels(connection):
    # Live: EC2 returns only these fields for tunnels created with default options.
    connection["Options"]["TunnelOptions"] = [
        {
            "OutsideIpAddress": address,
            "PreSharedKey": "EXAMPLE_GENERATED_SECRET",
            "TunnelInsideCidr": cidr,
            "LogOptions": {"CloudWatchLogOptions": {"LogEnabled": False, "BgpLogEnabled": False}},
        }
        for address, cidr in (("203.0.113.1", "169.254.10.0/30"), ("203.0.113.2", "169.254.11.0/30"))
    ]
    return connection


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("option", sorted(DEFAULT_TUNNEL_LISTS))
def test_omitted_tunnel_lists_match_explicit_aws_defaults(params, default_tunnels, check_mode, option):
    params["tunnel_options"] = [{option: DEFAULT_TUNNEL_LISTS[option]}]
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), default_tunnels)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("option", sorted(DEFAULT_TUNNEL_LISTS))
def test_omitted_tunnel_lists_change_for_non_default_values(params, default_tunnels, option):
    value = DEFAULT_TUNNEL_LISTS[option][:1]
    params["tunnel_options"] = [{option: value}]
    field = plugin.TUNNEL_FIELDS[option]
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == [
        (address, {field: [{"Value": value[0]}]}) for address in ("203.0.113.1", "203.0.113.2")
    ]


def test_omitted_tunnel_list_default_does_not_hide_a_returned_empty_list(params, default_tunnels):
    default_tunnels["Options"]["TunnelOptions"][0]["IkeVersions"] = []
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "ike_versions": ["ikev1", "ikev2"]}]
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == [
        ("203.0.113.1", {"IKEVersions": [{"Value": "ikev1"}, {"Value": "ikev2"}]})
    ]


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


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize(
    "selector, targets",
    [
        ({}, ["203.0.113.1", "203.0.113.2"]),
        ({"outside_ip_address": None}, ["203.0.113.1", "203.0.113.2"]),
        ({"outside_ip_address": "203.0.113.2"}, ["203.0.113.2"]),
        ({"outside_ip_address": ""}, None),
        ({"outside_ip_address": " "}, None),
    ],
    ids=["omitted", "null", "selected", "empty", "whitespace"],
)
def test_blank_tunnel_selector_fails_before_any_aws_call(module_spec, connection, check_mode, selector, targets):
    # An empty selector counted as omitted, so a single entry meant for one tunnel changed both.
    spec = {key: value for key, value in module_spec.items() if key != "supports_check_mode"}
    tunnel = dict(selector, phase1_encryption_algorithms=["AES256"])
    result = ArgumentSpecValidator(**spec).validate({"vpn_connection_id": "vpn-123", "tunnel_options": [tunnel]})
    assert not result.error_messages
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    module = FakeModule(result.validated_parameters, check_mode=check_mode, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(module, "client", wraps=module.client) as connect,
    ):
        if targets is None:
            with pytest.raises(ModuleFail) as raised:
                plugin.main()

            assert raised.value.values == {"msg": "tunnel_options[].outside_ip_address must not be empty"}
            connect.assert_not_called()
            assert client.mock_calls == []
            return

        with pytest.raises(ModuleExit) as exited:
            plugin.main()

    assert exited.value.values["changed"] is True
    modified = [call.kwargs["VpnTunnelOutsideIpAddress"] for call in client.modify_vpn_tunnel_options.call_args_list]
    assert modified == ([] if check_mode else targets)


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("blank", ["", " "])
def test_create_rejects_a_blank_tunnel_selector_before_any_aws_call(params, check_mode, blank):
    # Creation used to ignore an empty selector; no tunnel exists yet to select.
    params.update(
        customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123", tunnel_options=[{"outside_ip_address": blank}]
    )
    module = FakeModule(params, check_mode=check_mode)
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_inputs(module)
        plugin.ensure_present(client, module, None)

    assert raised.value.values == {"msg": "tunnel_options[].outside_ip_address must not be empty"}
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

    waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.20.0.0/16", changed=True)
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


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("blank", ["", " "])
@pytest.mark.parametrize(
    "gateways",
    [
        {"customer_gateway_id": None, "vpn_gateway_id": "vgw-123"},
        {"customer_gateway_id": "cgw-123", "vpn_gateway_id": None},
        {"customer_gateway_id": "cgw-123", "transit_gateway_id": None},
        {"customer_gateway_id": "cgw-123", "vpn_concentrator_id": None},
    ],
    ids=["customer_gateway_id", "vpn_gateway_id", "transit_gateway_id", "vpn_concentrator_id"],
)
def test_create_rejects_blank_gateway_ids_before_any_aws_call(params, check_mode, blank, gateways):
    # No gateway has a blank ID, so EC2 can never create the connection that check mode would predict.
    params.update({name: blank if value is None else value for name, value in gateways.items()})
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), None)

    assert raised.value.values == {
        "msg": "Creation requires name, customer_gateway_id, and one of vpn_gateway_id, transit_gateway_id, "
        "or vpn_concentrator_id"
    }
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("blank", ["", " "])
@pytest.mark.parametrize("option", ["vpn_gateway_id", "transit_gateway_id"])
def test_create_rejects_a_blank_gateway_id_next_to_a_concentrator(params, check_mode, blank, option):
    # Live: EC2 rejects an empty ID, but ignores a whitespace-only one and creates a concentrator connection that no
    # later run can match.
    params.update({"customer_gateway_id": "cgw-123", "vpn_concentrator_id": "vcn-123", option: blank})
    module = FakeModule(params, check_mode=check_mode)
    module.require_botocore_at_least = Mock()
    plugin.validate_inputs(module)
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, module, None)

    assert raised.value.values == {"msg": f"{option} must not be empty"}
    assert client.mock_calls == []


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


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("state", ["present", "absent"])
@pytest.mark.parametrize("option", ["name", "vpn_connection_id", "filters"])
def test_null_selector_is_rejected_before_any_aws_call(module_spec, option, state, check_mode):
    spec = dict(module_spec)
    spec.pop("supports_check_mode")
    # required_one_of counts only supplied keys, so ansible-core accepts an explicit null and keeps it None.
    result = ArgumentSpecValidator(**spec).validate({option: None, "state": state})

    assert not result.error_messages
    assert result.validated_parameters[option] is None

    module = FakeModule(result.validated_parameters, check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": "one of the following is required: name, vpn_connection_id, filters"}
    module.client.assert_not_called()


@pytest.mark.parametrize("state,changed", [("available", True), ("deleting", False)])
def test_delete_is_idempotent_and_waits(params, connection, state, changed, sdk_checks):
    connection["State"] = state
    client = Mock()
    with patch.object(plugin, "wait_for_connection_deleted") as waiter, pytest.raises(ModuleExit) as result:
        plugin.ensure_absent(client, FakeModule(params), connection)

    assert result.value.values == {"changed": changed, "vpn_connection": {}}
    assert bool(client.delete_vpn_connection.call_count) == changed
    waiter.assert_called_once_with(client, ANY, "vpn-123", changed=changed)
    client.get_waiter.assert_not_called()
    if changed:
        sdk_checks.assert_called_once_with(ANY, client, "EC2", {"delete_vpn_connection": ("VpnConnectionId",)})


def test_pending_connection_becomes_available_before_delete(params, connection):
    connection["State"] = "pending"
    client = Mock()
    client.attach_mock(Mock(), "wait_for_connection_deleted")
    with (
        patch.object(plugin, "wait_for_connection_deleted", client.wait_for_connection_deleted),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_absent(client, FakeModule(params), connection)

    assert result.value.values == {"changed": True, "vpn_connection": {}}
    # The deleted waiter fails on a pending connection, so deletion waits for available first.
    client.get_waiter.assert_called_once_with("vpn_connection_available")
    assert [
        call[0]
        for call in client.method_calls
        if call[0] in ("get_waiter", "delete_vpn_connection", "wait_for_connection_deleted")
    ] == [
        "get_waiter",
        "delete_vpn_connection",
        "wait_for_connection_deleted",
    ]


@pytest.mark.parametrize(
    "outcome,succeeds",
    [("deleted", True), ("not_found", True), ("pending", False)],
)
def test_deleted_waiter_treats_a_vanished_connection_as_deleted(params, outcome, succeeds):
    params.update(wait_delay=1, wait_timeout=600)
    client = Session().create_client(
        "ec2", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    describe = Mock(return_value={"VpnConnections": [{"VpnConnectionId": "vpn-123", "State": outcome}]})
    if outcome == "not_found":
        describe.side_effect = ClientError(
            {"Error": {"Code": "InvalidVpnConnectionID.NotFound", "Message": "VPN is missing"}},
            "DescribeVpnConnections",
        )

    with patch.object(client, "describe_vpn_connections", describe), patch("botocore.waiter.time.sleep") as sleep:
        if succeeds:
            plugin.wait_for_connection_deleted(client, FakeModule(params), "vpn-123", changed=True)
        else:
            with pytest.raises(ModuleFail, match="vpn-123 to become deleted") as failure:
                plugin.wait_for_connection_deleted(client, FakeModule(params), "vpn-123", changed=True)

            assert failure.value.values["changed"] is True

    describe.assert_called_once_with(VpnConnectionIds=["vpn-123"])
    sleep.assert_not_called()


def test_boolean_and_numeric_filter_list_entries_are_sent_as_strings(params, connection):
    params.update(name=None, filters={"customer-gateway-configuration": "x", "x-count": [2], "x-flag": [True]})
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    plugin.find_connection(client, FakeModule(params))

    client.describe_vpn_connections.assert_called_once_with(
        Filters=[
            {"Name": "customer-gateway-configuration", "Values": ["x"]},
            {"Name": "x-count", "Values": ["2"]},
            {"Name": "x-flag", "Values": ["true"]},
        ],
        aws_retry=True,
    )


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
def test_ipv6_creation_without_a_transit_gateway_fails_before_any_aws_call(params, check_mode):
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123", tunnel_inside_ip_version="ipv6")
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), None)

    assert raised.value.values == {"changed": False, "msg": "IPv6 VPN connections require a transit gateway"}
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
def test_existing_ipv6_connection_without_a_gateway_is_managed(params, connection, check_mode):
    # Live: EC2 creates an IPv6 connection attached to no gateway, which Cloud WAN can attach later.
    connection.pop("VpnGatewayId")
    connection["CoreNetworkArn"] = "arn:aws:networkmanager::123456789012:core-network/core-network-0123456789abcdef0"
    connection["Routes"] = []
    connection["Options"].pop("LocalIpv4NetworkCidr")
    connection["Options"].update(
        StaticRoutesOnly=False,
        TunnelInsideIpVersion="ipv6",
        LocalIpv6NetworkCidr="::/0",
        RemoteIpv6NetworkCidr="::/0",
    )
    params.update(name=None, vpn_connection_id="vpn-123")
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), connection)["changed"] is False
    assert client.mock_calls == []

    params.update(tags={"Probe": "x"}, purge_tags=False)
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    assert ensure(client, FakeModule(params, check_mode=check_mode), connection)["changed"] is True
    if check_mode:
        assert client.mock_calls == []
    else:
        assert [call[0] for call in client.mock_calls] == ["create_tags", "describe_vpn_connections"]
        client.create_tags.assert_called_once_with(
            Resources=["vpn-123"], Tags=[{"Key": "Probe", "Value": "x"}], aws_retry=True
        )


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


@pytest.mark.parametrize("option", ["local_ipv6_network_cidr", "remote_ipv6_network_cidr"])
@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("existing", [True, False])
def test_ipv6_network_cidr_rejected_on_ipv4_connection(params, connection, option, check_mode, existing):
    # EC2 rejects these options for an IPv4 connection on create and on modify, and omits them from it.
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123", **{option: "::/0"})
    client = Mock()
    module = FakeModule(params, check_mode=check_mode)
    plugin.validate_inputs(module)
    with pytest.raises(ModuleFail, match=f"{option} requires tunnel_inside_ip_version=ipv6"):
        plugin.ensure_present(client, module, connection if existing else None)

    assert client.mock_calls == []


@pytest.mark.parametrize("option", ["local_ipv6_network_cidr", "remote_ipv6_network_cidr"])
def test_ipv6_network_cidr_is_valid_on_ipv6_connection(params, option):
    params.update(transit_gateway_id="tgw-123", tunnel_inside_ip_version="ipv6", **{option: "::/0"})
    module = FakeModule(params)
    plugin.validate_inputs(module)
    plugin.validate_configuration(module)


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
        waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.0.0.0/8", changed=False)
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


@pytest.mark.parametrize("actual", [None, ""])
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
        waiter.assert_called_once_with(client, waiter.call_args.args[1], "vpn-123", "10.0.0.0/8", changed=False)
        assert result["vpn_connection"]["routes"][0]["state"] == "available"


@pytest.mark.parametrize(
    "routes,purge,check_mode", [([], True, False), ([], True, True), ([], False, False), (None, True, False)]
)
def test_purged_route_already_deleting_waits_without_another_delete(params, connection, routes, purge, check_mode):
    params.update(routes=routes, purge_routes=purge)
    connection["Routes"][0]["State"] = "deleting"
    final = deepcopy(connection)
    final["Routes"] = []
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [final]}
    module = FakeModule(params, check_mode=check_mode)
    with patch.object(plugin, "wait_for_route_deleted") as waiter:
        result = ensure(client, module, connection)

    assert result["changed"] is False
    client.delete_vpn_connection_route.assert_not_called()
    if routes is not None and purge and not check_mode:
        waiter.assert_called_once_with(client, module, "vpn-123", "10.0.0.0/8", changed=False)
        assert result["vpn_connection"]["routes"] == []
    else:
        waiter.assert_not_called()
        assert client.mock_calls == []


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


def test_update_checks_each_operation_and_parameter(params, connection, sdk_checks):
    params.update(
        local_ipv4_network_cidr="10.20.0.0/16",
        routes=["10.1.0.0/16"],
        tags={"Environment": "test"},
        tunnel_options=[{"outside_ip_address": "203.0.113.1", "phase1_encryption_algorithms": ["AES256"]}],
    )
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with (
        patch.object(plugin, "wait_for_connection"),
        patch.object(plugin, "wait_for_route_state"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, FakeModule(params), connection)

    checked = {}
    for call in sdk_checks.call_args_list:
        assert call.args[2] == "EC2"
        checked.update(call.args[3])

    assert checked == {
        "create_tags": ("Resources", "Tags"),
        "create_vpn_connection_route": ("DestinationCidrBlock", "VpnConnectionId"),
        "delete_tags": ("Resources", "Tags"),
        "delete_vpn_connection_route": ("DestinationCidrBlock", "VpnConnectionId"),
        "describe_vpn_connections": ("VpnConnectionIds",),
        "modify_vpn_connection_options": ("VpnConnectionId", "LocalIpv4NetworkCidr"),
        "modify_vpn_tunnel_options": ("TunnelOptions", "VpnConnectionId", "VpnTunnelOutsideIpAddress"),
    }
    real_client = Session().create_client("ec2", region_name="us-east-1")
    sdk.require_client_methods(FakeModule({}), real_client, "EC2", checked)


def test_create_checks_the_submitted_request(params, sdk_checks):
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123", static_only=True)
    client = Mock()
    client.create_vpn_connection.return_value = {
        "VpnConnection": {"VpnConnectionId": "vpn-123", "State": "pending", "Options": {}}
    }
    with (
        patch.object(plugin, "wait_for_connection"),
        patch.object(plugin, "read_connection", return_value={"VpnConnectionId": "vpn-123"}),
    ):
        plugin.create_connection(client, FakeModule(params))

    checked = sdk_checks.call_args.args[3]
    assert set(checked) == {"create_vpn_connection"}
    assert set(checked["create_vpn_connection"]) == set(client.create_vpn_connection.call_args.kwargs) - {"aws_retry"}
    real_client = Session().create_client("ec2", region_name="us-east-1")
    sdk.require_client_methods(FakeModule({}), real_client, "EC2", checked)


@pytest.mark.parametrize(("local_cidr", "changed"), [("10.0.0.0/8", True), (None, False)])
def test_tunnel_failure_reports_whether_options_were_modified(params, connection, local_cidr, changed):
    params.update(
        local_ipv4_network_cidr=local_cidr,
        tunnel_options=[{"outside_ip_address": "203.0.113.2", "phase1_encryption_algorithms": ["AES256"]}],
    )
    client = Mock()
    client.modify_vpn_tunnel_options.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "failed"}}, "ModifyVpnTunnelOptions"
    )
    with (
        patch.object(plugin, "wait_for_connection"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params), connection)

    assert raised.value.values["msg"] == "Unable to modify VPN connection vpn-123 tunnel 203.0.113.2"
    assert raised.value.values["changed"] is changed
    assert client.modify_vpn_connection_options.called is changed


def test_route_failure_after_tunnel_changes_reports_changed(params, connection):
    params.update(
        routes=["10.0.0.0/8", "10.20.0.0/16"],
        tunnel_options=[{"outside_ip_address": "203.0.113.2", "phase1_encryption_algorithms": ["AES256"]}],
    )
    client = Mock()
    client.create_vpn_connection_route.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "failed"}}, "CreateVpnConnectionRoute"
    )
    with (
        patch.object(plugin, "wait_for_connection"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params), connection)

    assert raised.value.values["msg"] == "Unable to create route 10.20.0.0/16 on VPN connection vpn-123"
    assert raised.value.values["changed"] is True


def test_unsupported_tagging_fails_before_modifying_options(params, connection, sdk_checks):
    params.update(local_ipv4_network_cidr="10.0.0.0/8", tags={"Env": "test"})

    def require(module, client, service, methods, changed=False):
        if "create_tags" in methods:
            module.fail_json(changed=changed, msg="Unsupported tagging")

    sdk_checks.side_effect = require
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params), connection)

    assert raised.value.values["changed"] is False
    client.modify_vpn_connection_options.assert_not_called()


def test_wait_failure_after_create_reports_changed(params, connection):
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123")
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": dict(connection, State="pending")}
    client.get_waiter.return_value.wait.side_effect = WaiterError("VpnConnectionAvailable", "failed", {})
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params), None)

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to wait for VPN connection vpn-123 to become available"


@pytest.mark.parametrize("name", ["branch-*", "branch-?"])
def test_name_lookup_treats_wildcard_characters_literally(params, connection, name):
    def named(connection_id, connection_name):
        return dict(
            deepcopy(connection), VpnConnectionId=connection_id, Tags=[{"Key": "Name", "Value": connection_name}]
        )

    wildcard_matches = [named("vpn-a", "branch-a"), named("vpn-b", "branch-b")]
    exact = named("vpn-exact", name)
    params.update(name=name)
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": wildcard_matches + [exact]}
    module = FakeModule(params)
    assert plugin.find_connection(client, module) == exact
    client.describe_vpn_connections.assert_called_once_with(
        Filters=[{"Name": "tag:Name", "Values": [name]}], aws_retry=True
    )

    client.describe_vpn_connections.return_value = {"VpnConnections": wildcard_matches}
    assert plugin.find_connection(client, module) is None


@pytest.mark.parametrize("check_mode", [False, True])
def test_resulting_tag_limit_fails_before_any_write(params, connection, check_mode):
    connection["Tags"] += [{"Key": f"old{index}", "Value": ""} for index in range(48)]
    connection["Tags"].append({"Key": "aws:reserved", "Value": ""})
    params.update(
        purge_routes=False,
        purge_tags=False,
        routes=["10.0.0.0/8", "192.168.0.0/16"],
        tags={"Env": "test"},
        tunnel_options=[{"ike_versions": ["ikev2"]}],
    )
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert raised.value.values["msg"] == "The resulting VPN connection tags must contain at most 50 entries"
    assert raised.value.values.get("changed", False) is False
    assert client.mock_calls == []


@pytest.fixture
def transit_connection(connection):
    connection.pop("VpnGatewayId")
    connection["TransitGatewayId"] = "tgw-123"
    connection["Options"]["TunnelBandwidth"] = "standard"
    return connection


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("current", ["standard", "large", None])
@pytest.mark.parametrize("desired", ["standard", "large"])
def test_tunnel_bandwidth_converges_and_reruns_without_change(params, transit_connection, check_mode, current, desired):
    # Live: EC2 returns TunnelBandwidth for every connection; the model documents standard when it is unset.
    if current is None:
        transit_connection["Options"].pop("TunnelBandwidth")
    else:
        transit_connection["Options"]["TunnelBandwidth"] = current

    params["tunnel_bandwidth"] = desired
    updated = deepcopy(transit_connection)
    updated["Options"]["TunnelBandwidth"] = desired
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    changed = desired != (current or "standard")
    with patch.object(plugin, "wait_for_connection") as waiter:
        result = ensure(client, FakeModule(params, check_mode=check_mode), transit_connection)

    assert result["changed"] is changed
    if check_mode or not changed:
        assert client.mock_calls == []
        assert result["vpn_connection"] == plugin.normalize_connection(transit_connection)
    else:
        client.modify_vpn_connection_options.assert_called_once_with(
            VpnConnectionId="vpn-123", TunnelBandwidth=desired, aws_retry=True
        )
        waiter.assert_called_once_with(client, ANY, "vpn-123", changed=True)
        assert result["vpn_connection"]["options"]["tunnel_bandwidth"] == desired

    client.reset_mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), updated)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("current", ["standard", "large", None])
def test_omitted_tunnel_bandwidth_leaves_connection_unchanged(params, transit_connection, current):
    if current is None:
        transit_connection["Options"].pop("TunnelBandwidth")
    else:
        transit_connection["Options"]["TunnelBandwidth"] = current

    client = Mock()
    assert ensure(client, FakeModule(params), transit_connection)["changed"] is False
    assert client.mock_calls == []


def test_tunnel_bandwidth_and_cidr_change_in_one_request(params, transit_connection, sdk_checks):
    params.update(tunnel_bandwidth="large", local_ipv4_network_cidr="10.20.0.0/16")
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [transit_connection]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params), transit_connection)["changed"]

    client.modify_vpn_connection_options.assert_called_once_with(
        VpnConnectionId="vpn-123", LocalIpv4NetworkCidr="10.20.0.0/16", TunnelBandwidth="large", aws_retry=True
    )
    request = dict(client.modify_vpn_connection_options.call_args.kwargs)
    request.pop("aws_retry")
    validate_parameters(
        request, Session().get_service_model("ec2").operation_model("ModifyVpnConnectionOptions").input_shape
    )
    (checked,) = [call.args[3] for call in sdk_checks.call_args_list if "modify_vpn_connection_options" in call.args[3]]
    assert set(checked["modify_vpn_connection_options"]) == set(request)


def test_creation_sends_tunnel_bandwidth_without_a_follow_up_change(params, transit_connection):
    params.update(customer_gateway_id="cgw-123", transit_gateway_id="tgw-123", tunnel_bandwidth="large")
    created = deepcopy(transit_connection)
    created["Options"]["TunnelBandwidth"] = "large"
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": created}
    client.describe_vpn_connections.return_value = {"VpnConnections": [created]}
    with patch.object(plugin, "wait_for_connection"):
        result = ensure(client, FakeModule(params), None)

    assert result["changed"] is True
    assert result["vpn_connection"]["options"]["tunnel_bandwidth"] == "large"
    request = dict(client.create_vpn_connection.call_args.kwargs)
    assert request.pop("aws_retry") is True
    assert request["Options"] == {"TunnelBandwidth": "large"}
    validate_parameters(request, Session().get_service_model("ec2").operation_model("CreateVpnConnection").input_shape)
    client.modify_vpn_connection_options.assert_not_called()


def test_region_rejecting_a_tunnel_bandwidth_change_leaves_the_connection_unchanged(params, transit_connection):
    # Live (us-west-2): ModifyVpnConnectionOptions rejects any TunnelBandwidth, alone or with a CIDR change.
    params.update(tunnel_bandwidth="large", local_ipv4_network_cidr="10.20.0.0/16", tags={"Env": "test"})
    client = Mock()
    client.modify_vpn_connection_options.side_effect = ClientError(
        {"Error": {"Code": "UnsupportedOperation", "Message": "TunnelBandwidth parameter is not supported"}},
        "ModifyVpnConnectionOptions",
    )
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params), transit_connection)

    assert raised.value.values == {"changed": False, "msg": "Unable to modify options for VPN connection vpn-123"}
    assert [call[0] for call in client.mock_calls] == ["modify_vpn_connection_options"]


def test_unsupported_tunnel_bandwidth_update_fails_before_any_write(params, transit_connection, sdk_checks):
    # botocore 1.40.71 to 1.43.2 can create with TunnelBandwidth but cannot send it to ModifyVpnConnectionOptions.
    params.update(tunnel_bandwidth="large", tags={"Env": "test"})

    def require(module, client, service, methods, changed=False):
        if "TunnelBandwidth" in methods.get("modify_vpn_connection_options", ()):
            module.fail_json(changed=changed, msg="Unsupported TunnelBandwidth")

    sdk_checks.side_effect = require
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params), transit_connection)

    assert raised.value.values == {"changed": False, "msg": "Unsupported TunnelBandwidth"}
    assert client.mock_calls == []


@pytest.mark.parametrize("state", ["present", "absent"])
@pytest.mark.parametrize(
    "option, value, version",
    [
        ("tunnel_bandwidth", "standard", "1.40.71"),
        ("tunnel_bandwidth", "large", "1.40.71"),
        ("pre_shared_key_storage", "Standard", "1.38.24"),
        ("pre_shared_key_storage", "SecretsManager", "1.38.24"),
        ("vpn_concentrator_id", "vcn-123", "1.40.76"),
        ("tunnel_bandwidth", None, None),
        ("vpn_concentrator_id", None, None),
    ],
)
def test_new_options_require_botocore_only_when_supplied(params, state, option, value, version):
    params.update({"state": state, option: value})
    module = FakeModule(params)
    module.require_botocore_at_least = Mock(side_effect=ModuleFail({"msg": "botocore"}))
    if state == "present" and value is not None:
        with pytest.raises(ModuleFail, match="botocore"):
            plugin.validate_inputs(module)

        module.require_botocore_at_least.assert_called_once_with(version, reason=f"for {option}")
    else:
        plugin.validate_inputs(module)
        module.require_botocore_at_least.assert_not_called()


def stored_in_secrets_manager(connection, *addresses):
    # Live: EC2 omits PreSharedKey from a tunnel that stores it in Secrets Manager and returns the secret ARN.
    for tunnel in connection["Options"]["TunnelOptions"]:
        if tunnel["OutsideIpAddress"] in addresses:
            tunnel.pop("PreSharedKey")

    connection["PreSharedKeyArn"] = "arn:aws:secretsmanager:us-east-1:123456789012:secret:s2svpn!vpn-123-EXAMPLE"
    return connection


@pytest.mark.parametrize(
    "stored, storage, targets",
    [
        ((), "Standard", []),
        ((), "SecretsManager", ["203.0.113.1", "203.0.113.2"]),
        (("203.0.113.2",), "Standard", ["203.0.113.2"]),
        (("203.0.113.2",), "SecretsManager", ["203.0.113.1"]),
        (("203.0.113.1", "203.0.113.2"), "SecretsManager", []),
        (("203.0.113.1", "203.0.113.2"), "Standard", ["203.0.113.1", "203.0.113.2"]),
        ((), None, []),
    ],
)
def test_storage_targets_compare_each_tunnel(params, connection, stored, storage, targets):
    if stored:
        stored_in_secrets_manager(connection, *stored)

    params["pre_shared_key_storage"] = storage
    assert plugin.storage_targets(FakeModule(params), connection) == targets


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("storage", ["Standard", "SecretsManager"])
def test_key_storage_converges_per_tunnel_and_reruns_without_change(params, connection, check_mode, storage):
    # Live: a tunnel keeps its key when its storage changes, and the secret ARN stays after both move to Standard.
    secrets_manager = stored_in_secrets_manager(deepcopy(connection), "203.0.113.1", "203.0.113.2")
    standard = dict(deepcopy(connection), PreSharedKeyArn=secrets_manager["PreSharedKeyArn"])
    current, updated = (secrets_manager, standard) if storage == "Standard" else (standard, secrets_manager)
    params["pre_shared_key_storage"] = storage
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    with patch.object(plugin, "wait_for_connection") as waiter:
        client.attach_mock(waiter, "wait_connection")
        result = ensure(client, FakeModule(params, check_mode=check_mode), current)

    assert result["changed"] is True
    if check_mode:
        assert client.mock_calls == []
        assert result["vpn_connection"] == plugin.normalize_connection(current)
    else:
        assert [call[0] for call in client.mock_calls] == [
            "modify_vpn_tunnel_options",
            "wait_connection",
            "modify_vpn_tunnel_options",
            "wait_connection",
            "describe_vpn_connections",
        ]
        shape = Session().get_service_model("ec2").operation_model("ModifyVpnTunnelOptions").input_shape
        for call, address in zip(client.modify_vpn_tunnel_options.call_args_list, ["203.0.113.1", "203.0.113.2"]):
            assert call.kwargs == {
                "VpnConnectionId": "vpn-123",
                "VpnTunnelOutsideIpAddress": address,
                "TunnelOptions": {},
                "PreSharedKeyStorage": storage,
                "aws_retry": True,
            }
            validate_parameters({key: value for key, value in call.kwargs.items() if key != "aws_retry"}, shape)

        assert result["vpn_connection"] == plugin.normalize_connection(updated)

    client.reset_mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), updated)["changed"] is False
    assert client.mock_calls == []


def test_key_storage_change_joins_the_tunnels_other_changes(params, connection, sdk_checks):
    params.update(
        pre_shared_key_storage="SecretsManager",
        tunnel_options=[{"outside_ip_address": "203.0.113.2", "phase1_encryption_algorithms": ["AES256"]}],
    )
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params), connection)["changed"]

    assert [call.kwargs for call in client.modify_vpn_tunnel_options.call_args_list] == [
        {
            "VpnConnectionId": "vpn-123",
            "VpnTunnelOutsideIpAddress": "203.0.113.2",
            "TunnelOptions": {"Phase1EncryptionAlgorithms": [{"Value": "AES256"}]},
            "PreSharedKeyStorage": "SecretsManager",
            "aws_retry": True,
        },
        {
            "VpnConnectionId": "vpn-123",
            "VpnTunnelOutsideIpAddress": "203.0.113.1",
            "TunnelOptions": {},
            "PreSharedKeyStorage": "SecretsManager",
            "aws_retry": True,
        },
    ]
    (checked,) = [call.args[3] for call in sdk_checks.call_args_list if "modify_vpn_tunnel_options" in call.args[3]]
    assert checked["modify_vpn_tunnel_options"] == (
        "TunnelOptions",
        "VpnConnectionId",
        "VpnTunnelOutsideIpAddress",
        "PreSharedKeyStorage",
    )
    sdk.require_client_methods(FakeModule({}), Session().create_client("ec2", region_name="us-east-1"), "EC2", checked)


@pytest.mark.parametrize("check_mode", [True, False])
def test_moving_a_key_out_of_secrets_manager_sets_the_supplied_key(params, connection, check_mode):
    # Live: ModifyVpnTunnelOptions accepts PreSharedKey with PreSharedKeyStorage=Standard and returns the new key.
    stored_in_secrets_manager(connection, "203.0.113.2")
    params.update(
        pre_shared_key_storage="Standard",
        tunnel_options=[{"outside_ip_address": "203.0.113.2", "pre_shared_key": "EXAMPLE_REPLACEMENT"}],
    )
    updated = deepcopy(connection)
    updated["Options"]["TunnelOptions"][1]["PreSharedKey"] = "EXAMPLE_REPLACEMENT"
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params, check_mode=check_mode), connection)["changed"] is True

    if check_mode:
        assert client.mock_calls == []
    else:
        client.modify_vpn_tunnel_options.assert_called_once_with(
            VpnConnectionId="vpn-123",
            VpnTunnelOutsideIpAddress="203.0.113.2",
            TunnelOptions={"PreSharedKey": "EXAMPLE_REPLACEMENT"},
            PreSharedKeyStorage="Standard",
            aws_retry=True,
        )

    client.reset_mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), updated)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
def test_key_in_secrets_manager_without_storage_option_still_cannot_be_compared(params, connection, check_mode):
    stored_in_secrets_manager(connection, "203.0.113.1")
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "pre_shared_key": "EXAMPLE_REPLACEMENT"}]
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert "EXAMPLE_REPLACEMENT" not in str(raised.value)
    assert raised.value.values["msg"].endswith(
        "Omit pre_shared_key to leave it unchanged, or set pre_shared_key_storage=Standard to replace it."
    )
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("existing", [True, False])
def test_explicit_key_with_secrets_manager_storage_fails_before_any_aws_call(params, connection, check_mode, existing):
    # Live: CreateVpnConnection stores supplied keys in the secret, but EC2 never returns them, so reruns could not compare.
    params.update(
        customer_gateway_id="cgw-123",
        vpn_gateway_id="vgw-123",
        pre_shared_key_storage="SecretsManager",
        tunnel_options=[{"pre_shared_key": "EXAMPLE_DESIRED_SECRET"}],
    )
    module = FakeModule(params, check_mode=check_mode)
    module.require_botocore_at_least = Mock()
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_inputs(module)
        plugin.ensure_present(client, module, connection if existing else None)

    assert raised.value.values == {
        "msg": "tunnel_options[].pre_shared_key cannot be used with pre_shared_key_storage=SecretsManager because "
        "EC2 does not return keys stored in Secrets Manager for comparison"
    }
    assert client.mock_calls == []


def test_creation_sends_key_storage_without_a_follow_up_change(params, connection, sdk_checks):
    params.update(customer_gateway_id="cgw-123", vpn_gateway_id="vgw-123", pre_shared_key_storage="SecretsManager")
    # Live: the CreateVpnConnection response omits both the keys and the secret ARN while pending.
    created = deepcopy(connection)
    created["State"] = "pending"
    for tunnel in created["Options"]["TunnelOptions"]:
        tunnel.pop("PreSharedKey")

    available = stored_in_secrets_manager(deepcopy(connection), "203.0.113.1", "203.0.113.2")
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": created}
    client.describe_vpn_connections.return_value = {"VpnConnections": [available]}
    with patch.object(plugin, "wait_for_connection"):
        result = ensure(client, FakeModule(params), None)

    assert result["changed"] is True
    assert result["vpn_connection"]["pre_shared_key_arn"] == available["PreSharedKeyArn"]
    request = dict(client.create_vpn_connection.call_args.kwargs)
    assert request.pop("aws_retry") is True
    assert request["PreSharedKeyStorage"] == "SecretsManager"
    validate_parameters(request, Session().get_service_model("ec2").operation_model("CreateVpnConnection").input_shape)
    checked = sdk_checks.call_args_list[0].args[3]
    assert set(checked["create_vpn_connection"]) == set(request)
    client.modify_vpn_tunnel_options.assert_not_called()


@pytest.mark.parametrize("current", [None, [], [{"OutsideIpAddress": "203.0.113.1"}, {}]])
def test_pending_vpn_check_mode_predicts_unresolved_key_storage(params, connection, current):
    connection["State"] = "pending"
    connection["Options"]["TunnelOptions"] = current
    params["pre_shared_key_storage"] = "Standard"
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=True), connection)["changed"] is True
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
def test_key_storage_without_returned_tunnels_fails_before_any_write(params, connection, check_mode):
    connection["Options"]["TunnelOptions"] = None
    params.update(pre_shared_key_storage="Standard", local_ipv4_network_cidr="10.20.0.0/16")
    client = Mock()
    with pytest.raises(ModuleFail, match="EC2 did not return the requested tunnels"):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert client.mock_calls == []


LOG_GROUP_ARN = "arn:aws:logs:us-east-1:123456789012:log-group:EXAMPLE-vpn-logs"

NONDEFAULT_TUNNEL = {
    "phase1_lifetime_seconds": 27000,
    "phase2_lifetime_seconds": 3000,
    "rekey_margin_time_seconds": 1500,
    "rekey_fuzz_percentage": 50,
    "replay_window_size": 2048,
    "dpd_timeout_seconds": 45,
    "dpd_timeout_action": "restart",
    "startup_action": "start",
    "enable_tunnel_lifecycle_control": True,
    "log_options": {
        "cloud_watch_log_options": {
            "log_enabled": True,
            "log_group_arn": LOG_GROUP_ARN,
            "log_output_format": "text",
            "bgp_log_enabled": True,
            "bgp_log_group_arn": LOG_GROUP_ARN,
            "bgp_log_output_format": "text",
        }
    },
}

NONDEFAULT_LOGS = {
    "LogEnabled": True,
    "LogGroupArn": LOG_GROUP_ARN,
    "LogOutputFormat": "text",
    "BgpLogEnabled": True,
    "BgpLogGroupArn": LOG_GROUP_ARN,
    "BgpLogOutputFormat": "text",
}

# Live: EC2 returns these fields, with Dpd casing, once NONDEFAULT_TUNNEL is set.
NONDEFAULT_RESPONSE = {
    "Phase1LifetimeSeconds": 27000,
    "Phase2LifetimeSeconds": 3000,
    "RekeyMarginTimeSeconds": 1500,
    "RekeyFuzzPercentage": 50,
    "ReplayWindowSize": 2048,
    "DpdTimeoutSeconds": 45,
    "DpdTimeoutAction": "restart",
    "StartupAction": "start",
    "EnableTunnelLifecycleControl": True,
    "LogOptions": {"CloudWatchLogOptions": NONDEFAULT_LOGS},
}

NONDEFAULT_REQUEST = {
    "Phase1LifetimeSeconds": 27000,
    "Phase2LifetimeSeconds": 3000,
    "RekeyMarginTimeSeconds": 1500,
    "RekeyFuzzPercentage": 50,
    "ReplayWindowSize": 2048,
    "DPDTimeoutSeconds": 45,
    "DPDTimeoutAction": "restart",
    "StartupAction": "start",
    "EnableTunnelLifecycleControl": True,
    "LogOptions": {"CloudWatchLogOptions": NONDEFAULT_LOGS},
}

# AWS defaults of the tunnel options that EC2 omits until they are set.
DEFAULT_TUNNEL_SCALARS = {
    "phase1_lifetime_seconds": 28800,
    "phase2_lifetime_seconds": 3600,
    "rekey_margin_time_seconds": 270,
    "rekey_fuzz_percentage": 100,
    "replay_window_size": 1024,
    "dpd_timeout_action": "clear",
    "startup_action": "add",
    "enable_tunnel_lifecycle_control": False,
    "log_options": {
        "cloud_watch_log_options": {
            "log_enabled": False,
            "log_output_format": "json",
            "bgp_log_enabled": False,
            "bgp_log_output_format": "json",
        }
    },
}


def modify_shape():
    return Session().get_service_model("ec2").operation_model("ModifyVpnTunnelOptions").input_shape


def create_shape():
    return Session().get_service_model("ec2").operation_model("CreateVpnConnection").input_shape


@pytest.mark.parametrize("check_mode", [True, False])
def test_new_tunnel_options_converge_and_rerun_without_change(params, default_tunnels, check_mode):
    params["tunnel_options"] = [deepcopy(NONDEFAULT_TUNNEL)]
    updated = deepcopy(default_tunnels)
    for tunnel in updated["Options"]["TunnelOptions"]:
        tunnel.update(deepcopy(NONDEFAULT_RESPONSE))

    validate_parameters(
        updated["Options"]["TunnelOptions"][0], Session().get_service_model("ec2").shape_for("TunnelOption")
    )
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [updated]}
    with patch.object(plugin, "wait_for_connection") as waiter:
        result = ensure(client, FakeModule(params, check_mode=check_mode), default_tunnels)

    assert result["changed"] is True
    if check_mode:
        assert client.mock_calls == []
        waiter.assert_not_called()
    else:
        assert [call.kwargs for call in client.modify_vpn_tunnel_options.call_args_list] == [
            {
                "VpnConnectionId": "vpn-123",
                "VpnTunnelOutsideIpAddress": address,
                "TunnelOptions": NONDEFAULT_REQUEST,
                "aws_retry": True,
            }
            for address in ("203.0.113.1", "203.0.113.2")
        ]
        for call in client.modify_vpn_tunnel_options.call_args_list:
            validate_parameters(
                {key: value for key, value in call.kwargs.items() if key != "aws_retry"}, modify_shape()
            )

        assert waiter.call_count == 2
        tunnel = result["vpn_connection"]["options"]["tunnel_options"][0]
        assert tunnel["dpd_timeout_seconds"] == 45
        assert tunnel["log_options"]["cloud_watch_log_options"]["bgp_log_group_arn"] == LOG_GROUP_ARN

    client.reset_mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), updated)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("option", sorted(DEFAULT_TUNNEL_SCALARS))
def test_omitted_tunnel_scalars_match_explicit_aws_defaults(params, default_tunnels, check_mode, option):
    # Live: EC2 omits these until they are set; the lifetimes match the customer gateway configuration.
    params["tunnel_options"] = [{option: deepcopy(DEFAULT_TUNNEL_SCALARS[option])}]
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), default_tunnels)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("value", [30, 40])
def test_unset_dpd_timeout_is_sent_once(params, default_tunnels, value):
    # The EC2 API documents both 30 and 40 as the default of a timeout EC2 omits until it is set.
    params["tunnel_options"] = [{"dpd_timeout_seconds": value}]
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == [
        (address, {"DPDTimeoutSeconds": value}) for address in ("203.0.113.1", "203.0.113.2")
    ]
    for tunnel in default_tunnels["Options"]["TunnelOptions"]:
        tunnel["DpdTimeoutSeconds"] = value

    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == []


@pytest.mark.parametrize(
    "supplied, delta",
    [
        ({"log_enabled": False}, {"LogEnabled": False}),
        ({"log_group_arn": LOG_GROUP_ARN, "log_output_format": "text"}, None),
        ({"log_group_arn": f"{LOG_GROUP_ARN}:*"}, {"LogGroupArn": f"{LOG_GROUP_ARN}:*"}),
        ({"bgp_log_output_format": "json"}, {"BgpLogOutputFormat": "json"}),
        ({}, None),
    ],
)
def test_log_options_compare_and_send_only_supplied_fields(params, connection, supplied, delta):
    # Live: EC2 keeps the log fields an update omits and stores the ARN exactly as sent, with or without ":*".
    connection["Options"]["TunnelOptions"][0]["LogOptions"] = {"CloudWatchLogOptions": dict(NONDEFAULT_LOGS)}
    params["tunnel_options"] = [
        {"outside_ip_address": "203.0.113.1", "log_options": {"cloud_watch_log_options": supplied}}
    ]
    expected = [("203.0.113.1", {"LogOptions": {"CloudWatchLogOptions": delta}})] if delta else []
    assert plugin.tunnel_deltas(FakeModule(params), connection) == expected


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("enabled, group", [("log_enabled", "log_group_arn"), ("bgp_log_enabled", "bgp_log_group_arn")])
def test_enabling_logs_without_a_log_group_fails_before_any_write(params, default_tunnels, check_mode, enabled, group):
    # Live: EC2 rejects enabling logs on a tunnel without a log group, and reuses one already set on the tunnel.
    first = default_tunnels["Options"]["TunnelOptions"][0]
    first["LogOptions"]["CloudWatchLogOptions"][plugin.LOG_FIELDS[group]] = LOG_GROUP_ARN
    params.update(
        local_ipv4_network_cidr="10.20.0.0/16",
        tunnel_options=[{"log_options": {"cloud_watch_log_options": {enabled: True}}}],
    )
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), default_tunnels)

    assert raised.value.values == {
        "msg": f"Cannot update VPN connection vpn-123 tunnel 203.0.113.2: {enabled} requires {group}, which is "
        "neither supplied nor set on the tunnel"
    }
    assert client.mock_calls == []
    params["tunnel_options"][0]["log_options"]["cloud_watch_log_options"][group] = LOG_GROUP_ARN
    assert [change[0] for change in plugin.tunnel_deltas(FakeModule(params), default_tunnels)] == [
        "203.0.113.1",
        "203.0.113.2",
    ]
    params["tunnel_options"] = [
        {"outside_ip_address": "203.0.113.1", "log_options": {"cloud_watch_log_options": {enabled: True}}}
    ]
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == [
        ("203.0.113.1", {"LogOptions": {"CloudWatchLogOptions": {plugin.LOG_FIELDS[enabled]: True}}})
    ]


OTHER_LOG_GROUP_ARN = "arn:aws:logs:us-east-1:123456789012:log-group:EXAMPLE-other-logs"


def log_tunnel_params(module_spec, cloud_watch, outside_ip_address=None):
    # Built through the argument spec, so every omitted option is present as None, as in a real run.
    spec = {key: value for key, value in module_spec.items() if key != "supports_check_mode"}
    tunnel = {"log_options": {"cloud_watch_log_options": cloud_watch}}
    if outside_ip_address:
        tunnel["outside_ip_address"] = outside_ip_address

    result = ArgumentSpecValidator(**spec).validate({"vpn_connection_id": "vpn-123", "tunnel_options": [tunnel]})
    assert not result.error_messages
    return result.validated_parameters


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("prefix", ["", "bgp_"], ids=["log", "bgp_log"])
@pytest.mark.parametrize("log_enabled", [False, None], ids=["disabled", "omitted"])
@pytest.mark.parametrize("stored", [None, "", OTHER_LOG_GROUP_ARN], ids=["never_set", "empty", "other"])
@pytest.mark.parametrize("arn", [LOG_GROUP_ARN, " "], ids=["arn", "whitespace"])
def test_log_group_arn_is_ignored_while_its_logging_stays_disabled(
    module_spec, default_tunnels, check_mode, prefix, log_enabled, stored, arn
):
    # Live: while that logging stays disabled, EC2 accepts a log group ARN but keeps the stored one, so sending it
    # reported a change on every run.
    if stored is not None:
        for tunnel in default_tunnels["Options"]["TunnelOptions"]:
            tunnel["LogOptions"]["CloudWatchLogOptions"][plugin.LOG_FIELDS[f"{prefix}log_group_arn"]] = stored

    params = log_tunnel_params(module_spec, {f"{prefix}log_enabled": log_enabled, f"{prefix}log_group_arn": arn})
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), default_tunnels)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("prefix", ["", "bgp_"], ids=["log", "bgp_log"])
@pytest.mark.parametrize(
    "current, supplied, delta",
    [
        # Live: "" is accepted while logging is disabled and is the only way to clear a stored log group.
        ({"log_group_arn": LOG_GROUP_ARN}, {"log_group_arn": ""}, {"log_group_arn": ""}),
        (
            {"log_group_arn": LOG_GROUP_ARN},
            {"log_enabled": False, "log_group_arn": ""},
            {"log_enabled": False, "log_group_arn": ""},
        ),
        (
            {"log_enabled": True, "log_group_arn": LOG_GROUP_ARN},
            {"log_group_arn": OTHER_LOG_GROUP_ARN},
            {"log_group_arn": OTHER_LOG_GROUP_ARN},
        ),
        (
            {"log_enabled": True, "log_group_arn": LOG_GROUP_ARN},
            {"log_enabled": True, "log_group_arn": OTHER_LOG_GROUP_ARN},
            {"log_enabled": True, "log_group_arn": OTHER_LOG_GROUP_ARN},
        ),
        (
            {},
            {"log_enabled": True, "log_group_arn": LOG_GROUP_ARN},
            {"log_enabled": True, "log_group_arn": LOG_GROUP_ARN},
        ),
        (
            {"log_group_arn": LOG_GROUP_ARN},
            {"log_enabled": True, "log_group_arn": OTHER_LOG_GROUP_ARN},
            {"log_enabled": True, "log_group_arn": OTHER_LOG_GROUP_ARN},
        ),
        # A log group whose logging this run disables or leaves disabled is left out of other changes.
        (
            {"log_enabled": True, "log_group_arn": LOG_GROUP_ARN},
            {"log_enabled": False, "log_group_arn": OTHER_LOG_GROUP_ARN},
            {"log_enabled": False},
        ),
        ({}, {"log_group_arn": LOG_GROUP_ARN, "log_output_format": "text"}, {"log_output_format": "text"}),
    ],
    ids=[
        "clear",
        "disable_and_clear",
        "enabled_change",
        "enabled_explicit_change",
        "enable_with_arn",
        "enable_with_other_arn",
        "disable_with_arn",
        "disabled_other_change",
    ],
)
def test_log_group_arn_is_sent_while_its_logging_is_enabled_or_to_clear_it(
    module_spec, default_tunnels, check_mode, prefix, current, supplied, delta
):
    first = default_tunnels["Options"]["TunnelOptions"][0]
    first["LogOptions"]["CloudWatchLogOptions"].update(
        {plugin.LOG_FIELDS[prefix + name]: value for name, value in current.items()}
    )
    params = log_tunnel_params(module_spec, {prefix + name: value for name, value in supplied.items()}, "203.0.113.1")
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [default_tunnels]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params, check_mode=check_mode), default_tunnels)["changed"] is True

    if check_mode:
        assert client.mock_calls == []
    else:
        client.modify_vpn_tunnel_options.assert_called_once_with(
            VpnConnectionId="vpn-123",
            VpnTunnelOutsideIpAddress="203.0.113.1",
            TunnelOptions={
                "LogOptions": {
                    "CloudWatchLogOptions": {plugin.LOG_FIELDS[prefix + name]: value for name, value in delta.items()}
                }
            },
            aws_retry=True,
        )


def test_shared_log_group_arn_follows_each_tunnels_logging(module_spec, default_tunnels):
    first = default_tunnels["Options"]["TunnelOptions"][0]
    first["LogOptions"]["CloudWatchLogOptions"].update(LogEnabled=True, LogGroupArn=LOG_GROUP_ARN)
    params = log_tunnel_params(module_spec, {"log_group_arn": OTHER_LOG_GROUP_ARN})
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == [
        ("203.0.113.1", {"LogOptions": {"CloudWatchLogOptions": {"LogGroupArn": OTHER_LOG_GROUP_ARN}}})
    ]


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("actual", ["EXAMPLE", ["EXAMPLE"], {"CloudWatchLogOptions": "EXAMPLE"}])
def test_malformed_log_options_fail_before_mutation(params, connection, check_mode, actual):
    connection["Options"]["TunnelOptions"][1]["LogOptions"] = actual
    params.update(
        local_ipv4_network_cidr="10.20.0.0/16",
        tunnel_options=[{"log_options": {"cloud_watch_log_options": {"log_enabled": False}}}],
    )
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert raised.value.values == {
        "msg": "EC2 returned invalid LogOptions for VPN connection vpn-123 tunnel 203.0.113.2"
    }
    assert client.mock_calls == []


@pytest.mark.parametrize(
    "tunnel",
    [
        {"phase1_lifetime_seconds": 899},
        {"phase1_lifetime_seconds": 28801},
        {"phase2_lifetime_seconds": 899},
        {"phase2_lifetime_seconds": 3601},
        {"rekey_margin_time_seconds": 59},
        {"rekey_fuzz_percentage": -1},
        {"rekey_fuzz_percentage": 101},
        {"replay_window_size": 63},
        {"replay_window_size": 2049},
        {"dpd_timeout_seconds": 29},
    ],
)
def test_out_of_range_tunnel_values_fail_before_any_aws_call(params, tunnel):
    # Live: EC2 rejects each of these values, and a tunnel update can follow other writes.
    params["tunnel_options"] = [tunnel]
    (name,) = tunnel
    low, high = plugin.TUNNEL_RANGES[name]
    limit = f"{low} or greater" if high is None else f"between {low} and {high}"
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_inputs(FakeModule(params))

    assert raised.value.values == {"msg": f"tunnel_options[].{name} must be {limit}"}


@pytest.mark.parametrize(
    "tunnel",
    [
        {
            "phase1_lifetime_seconds": 900,
            "phase2_lifetime_seconds": 900,
            "rekey_margin_time_seconds": 60,
            "rekey_fuzz_percentage": 0,
            "replay_window_size": 64,
            "dpd_timeout_seconds": 30,
        },
        {"phase1_lifetime_seconds": 28800, "phase2_lifetime_seconds": 3600, "rekey_fuzz_percentage": 100},
        {"replay_window_size": 2048, "dpd_timeout_seconds": 86400},
    ],
)
def test_boundary_tunnel_values_are_valid(params, tunnel):
    params["tunnel_options"] = [tunnel]
    plugin.validate_inputs(FakeModule(params))


PHASE2_ABOVE_PHASE1 = "phase2_lifetime_seconds ({}) must not exceed phase1_lifetime_seconds ({})"
MARGIN_ABOVE_HALF = "rekey_margin_time_seconds ({}) must not exceed half of phase2_lifetime_seconds ({})"


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize(
    "returned, tunnel, problems",
    [
        ({}, {"phase1_lifetime_seconds": 900}, [PHASE2_ABOVE_PHASE1.format(3600, 900)]),
        ({}, {"rekey_margin_time_seconds": 1801}, [MARGIN_ABOVE_HALF.format(1801, 3600)]),
        ({}, {"phase2_lifetime_seconds": 900, "rekey_margin_time_seconds": 451}, [MARGIN_ABOVE_HALF.format(451, 900)]),
        ({"Phase2LifetimeSeconds": 900}, {"rekey_margin_time_seconds": 451}, [MARGIN_ABOVE_HALF.format(451, 900)]),
        (
            {"Phase1LifetimeSeconds": 1200, "RekeyMarginTimeSeconds": 601},
            {"phase2_lifetime_seconds": 1201},
            [PHASE2_ABOVE_PHASE1.format(1201, 1200), MARGIN_ABOVE_HALF.format(601, 1201)],
        ),
    ],
)
def test_tunnel_timers_are_checked_against_current_values_before_any_write(
    params, default_tunnels, check_mode, returned, tunnel, problems
):
    # Live: EC2 rejects each of these; the module resends the timers already set, so it checks the resulting values.
    default_tunnels["Options"]["TunnelOptions"][1].update(returned)
    params.update(
        local_ipv4_network_cidr="10.20.0.0/16",
        tunnel_options=[dict(tunnel, outside_ip_address="203.0.113.2")],
    )
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), default_tunnels)

    assert raised.value.values == {
        "msg": "Cannot update VPN connection vpn-123 tunnel 203.0.113.2: " + "; ".join(problems)
    }
    assert client.mock_calls == []


@pytest.mark.parametrize(
    "returned, sent",
    [
        ({}, {"Phase1LifetimeSeconds": 1000, "Phase2LifetimeSeconds": 900}),
        (
            {"RekeyMarginTimeSeconds": 300},
            {"Phase1LifetimeSeconds": 1000, "Phase2LifetimeSeconds": 900, "RekeyMarginTimeSeconds": 300},
        ),
    ],
)
def test_timer_change_resends_the_timers_already_set(params, default_tunnels, returned, sent):
    # Live: with Phase2LifetimeSeconds 900 set, EC2 rejected Phase1LifetimeSeconds 1000 sent alone, because it checks
    # the request against the 3600 second default of the omitted phase 2 lifetime.
    tunnel = default_tunnels["Options"]["TunnelOptions"][0]
    tunnel.update(Phase1LifetimeSeconds=900, Phase2LifetimeSeconds=900, **returned)
    params["tunnel_options"] = [
        {"outside_ip_address": "203.0.113.1", "phase1_lifetime_seconds": 1000, "phase2_lifetime_seconds": 900}
    ]
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == [("203.0.113.1", sent)]
    tunnel["Phase1LifetimeSeconds"] = 1000
    assert plugin.tunnel_deltas(FakeModule(params), default_tunnels) == []


def test_tunnel_timers_accept_equal_lifetimes_and_a_margin_of_half(params, default_tunnels):
    # Live: EC2 accepted 900/900 lifetimes on update and a 1500 second margin with a 3000 second phase 2 lifetime.
    params["tunnel_options"] = [
        {"phase1_lifetime_seconds": 900, "phase2_lifetime_seconds": 900, "rekey_margin_time_seconds": 450}
    ]
    assert len(plugin.tunnel_deltas(FakeModule(params), default_tunnels)) == 2


@pytest.mark.parametrize("value", ["3600", True, 3600.0])
def test_malformed_returned_timers_fail_before_mutation(params, default_tunnels, value):
    default_tunnels["Options"]["TunnelOptions"][0]["Phase2LifetimeSeconds"] = value
    params["tunnel_options"] = [{"outside_ip_address": "203.0.113.1", "rekey_margin_time_seconds": 300}]
    with pytest.raises(ModuleFail, match="EC2 returned invalid Phase2LifetimeSeconds"):
        plugin.tunnel_deltas(FakeModule(params), default_tunnels)


def test_skip_tunnel_replacement_is_sent_only_with_a_lifecycle_change(params, default_tunnels, sdk_checks):
    # Live: with SkipTunnelReplacement=true, EC2 applied the lifecycle change without entering modifying.
    params.update(
        skip_tunnel_replacement=True,
        tunnel_options=[
            {"outside_ip_address": "203.0.113.1", "enable_tunnel_lifecycle_control": True},
            {"outside_ip_address": "203.0.113.2", "startup_action": "start"},
        ],
    )
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [default_tunnels]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params), default_tunnels)["changed"] is True

    assert [call.kwargs for call in client.modify_vpn_tunnel_options.call_args_list] == [
        {
            "VpnConnectionId": "vpn-123",
            "VpnTunnelOutsideIpAddress": "203.0.113.1",
            "TunnelOptions": {"EnableTunnelLifecycleControl": True},
            "SkipTunnelReplacement": True,
            "aws_retry": True,
        },
        {
            "VpnConnectionId": "vpn-123",
            "VpnTunnelOutsideIpAddress": "203.0.113.2",
            "TunnelOptions": {"StartupAction": "start"},
            "aws_retry": True,
        },
    ]
    for call in client.modify_vpn_tunnel_options.call_args_list:
        validate_parameters({key: value for key, value in call.kwargs.items() if key != "aws_retry"}, modify_shape())

    (checked,) = [call.args[3] for call in sdk_checks.call_args_list if "modify_vpn_tunnel_options" in call.args[3]]
    assert checked["modify_vpn_tunnel_options"][-1] == "SkipTunnelReplacement"
    sdk.require_client_methods(FakeModule({}), Session().create_client("ec2", region_name="us-east-1"), "EC2", checked)


@pytest.mark.parametrize("storage", [True, False])
def test_skipped_lifecycle_change_is_sent_alone_before_the_tunnels_other_changes(
    params, default_tunnels, sdk_checks, storage
):
    # Live: EC2 rejects SkipTunnelReplacement with a StartupAction change (UnsupportedOperation).
    params.update(
        skip_tunnel_replacement=True,
        pre_shared_key_storage="SecretsManager" if storage else None,
        tunnel_options=[
            {"outside_ip_address": "203.0.113.1", "enable_tunnel_lifecycle_control": True, "startup_action": "start"}
        ],
    )
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [default_tunnels]}
    with patch.object(plugin, "wait_for_connection") as waiter:
        client.attach_mock(waiter, "wait_connection")
        assert ensure(client, FakeModule(params), default_tunnels)["changed"] is True

    calls = [call for call in client.mock_calls if call[0] in ("modify_vpn_tunnel_options", "wait_connection")]
    expected = [
        ("203.0.113.1", {"EnableTunnelLifecycleControl": True}, {"SkipTunnelReplacement": True}),
        ("203.0.113.1", {"StartupAction": "start"}, {"PreSharedKeyStorage": "SecretsManager"} if storage else {}),
    ]
    if storage:
        expected.append(("203.0.113.2", {}, {"PreSharedKeyStorage": "SecretsManager"}))

    assert [call[0] for call in calls] == ["modify_vpn_tunnel_options", "wait_connection"] * len(expected)
    assert [call.kwargs for call in client.modify_vpn_tunnel_options.call_args_list] == [
        dict(
            VpnConnectionId="vpn-123",
            VpnTunnelOutsideIpAddress=address,
            TunnelOptions=options,
            aws_retry=True,
            **parameters,
        )
        for address, options, parameters in expected
    ]
    for call in client.modify_vpn_tunnel_options.call_args_list:
        validate_parameters({key: value for key, value in call.kwargs.items() if key != "aws_retry"}, modify_shape())


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize("skip", [True, False])
@pytest.mark.parametrize("tunnels", [None, [{"enable_tunnel_lifecycle_control": False}]])
def test_skip_tunnel_replacement_never_reports_a_change(params, default_tunnels, check_mode, skip, tunnels):
    params.update(skip_tunnel_replacement=skip, tunnel_options=tunnels)
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=check_mode), default_tunnels)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("skip", [None, False])
def test_omitted_or_false_skip_tunnel_replacement_is_not_sent(params, default_tunnels, sdk_checks, skip):
    # Live: SkipTunnelReplacement=false replaced the endpoint just as omitting it did.
    params.update(
        skip_tunnel_replacement=skip,
        tunnel_options=[{"outside_ip_address": "203.0.113.1", "enable_tunnel_lifecycle_control": True}],
    )
    client = Mock()
    client.describe_vpn_connections.return_value = {"VpnConnections": [default_tunnels]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params), default_tunnels)["changed"] is True

    client.modify_vpn_tunnel_options.assert_called_once_with(
        VpnConnectionId="vpn-123",
        VpnTunnelOutsideIpAddress="203.0.113.1",
        TunnelOptions={"EnableTunnelLifecycleControl": True},
        aws_retry=True,
    )
    (checked,) = [call.args[3] for call in sdk_checks.call_args_list if "modify_vpn_tunnel_options" in call.args[3]]
    assert "SkipTunnelReplacement" not in checked["modify_vpn_tunnel_options"]


def test_creation_sends_connection_and_tunnel_options(params, transit_connection, sdk_checks):
    params.update(
        customer_gateway_id="cgw-123",
        transit_gateway_id="tgw-123",
        enable_acceleration=True,
        outside_ip_address_type="PublicIpv4",
        skip_tunnel_replacement=True,
        tunnel_options=[deepcopy(NONDEFAULT_TUNNEL)],
    )
    transit_connection["Options"].update(EnableAcceleration=True, OutsideIpAddressType="PublicIpv4")
    for tunnel in transit_connection["Options"]["TunnelOptions"]:
        tunnel.update(deepcopy(NONDEFAULT_RESPONSE))

    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": transit_connection}
    client.describe_vpn_connections.return_value = {"VpnConnections": [transit_connection]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params), None)["changed"] is True

    request = dict(client.create_vpn_connection.call_args.kwargs)
    assert request.pop("aws_retry") is True
    assert "SkipTunnelReplacement" not in json.dumps(request)
    assert request["Options"] == {
        "EnableAcceleration": True,
        "OutsideIpAddressType": "PublicIpv4",
        "TunnelOptions": [NONDEFAULT_REQUEST, NONDEFAULT_REQUEST],
    }
    first, second = request["Options"]["TunnelOptions"]
    assert first["LogOptions"] is not second["LogOptions"]
    validate_parameters(request, create_shape())
    assert set(sdk_checks.call_args_list[0].args[3]["create_vpn_connection"]) == set(request)
    client.modify_vpn_tunnel_options.assert_not_called()
    client.reset_mock()
    assert ensure(client, FakeModule(params), transit_connection)["changed"] is False
    assert client.mock_calls == []


def test_creation_attaches_a_vpn_concentrator_instead_of_a_transit_gateway(params, connection, sdk_checks):
    # Live: EC2 rejects TransitGatewayId with VpnConcentratorId and then omits TransitGatewayId from the connection.
    connection.pop("VpnGatewayId")
    connection["VpnConcentratorId"] = "vcn-123"
    connection["Options"]["StaticRoutesOnly"] = False
    params.update(customer_gateway_id="cgw-123", vpn_concentrator_id="vcn-123")
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": connection}
    client.describe_vpn_connections.return_value = {"VpnConnections": [connection]}
    with patch.object(plugin, "wait_for_connection"):
        result = ensure(client, FakeModule(params), None)

    assert result["vpn_connection"]["vpn_concentrator_id"] == "vcn-123"
    request = dict(client.create_vpn_connection.call_args.kwargs)
    request.pop("aws_retry")
    assert request["VpnConcentratorId"] == "vcn-123"
    assert "TransitGatewayId" not in request and "VpnGatewayId" not in request
    validate_parameters(request, create_shape())
    assert set(sdk_checks.call_args_list[0].args[3]["create_vpn_connection"]) == set(request)
    client.reset_mock()
    assert ensure(client, FakeModule(params), connection)["changed"] is False
    assert client.mock_calls == []


def test_creation_sends_a_private_ipv4_transport_attachment(params, transit_connection):
    # Private IP VPN needs AWS Direct Connect, so this request is covered by unit tests only.
    params.update(
        customer_gateway_id="cgw-123",
        transit_gateway_id="tgw-123",
        outside_ip_address_type="PrivateIpv4",
        transport_transit_gateway_attachment_id="tgw-attach-123",
    )
    transit_connection["Options"].update(
        OutsideIpAddressType="PrivateIpv4", TransportTransitGatewayAttachmentId="tgw-attach-123"
    )
    client = Mock()
    client.create_vpn_connection.return_value = {"VpnConnection": transit_connection}
    client.describe_vpn_connections.return_value = {"VpnConnections": [transit_connection]}
    with patch.object(plugin, "wait_for_connection"):
        assert ensure(client, FakeModule(params), None)["changed"] is True

    request = dict(client.create_vpn_connection.call_args.kwargs)
    request.pop("aws_retry")
    assert request["Options"] == {
        "OutsideIpAddressType": "PrivateIpv4",
        "TransportTransitGatewayAttachmentId": "tgw-attach-123",
    }
    validate_parameters(request, create_shape())


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize(
    "option, value",
    [
        ("enable_acceleration", True),
        ("outside_ip_address_type", "Ipv6"),
        ("outside_ip_address_type", "PrivateIpv4"),
        ("transport_transit_gateway_attachment_id", "tgw-attach-123"),
        ("vpn_concentrator_id", "vcn-123"),
    ],
)
def test_create_only_connection_options_fail_before_mutation(params, connection, check_mode, option, value):
    # No EC2 operation modifies these on an existing connection.
    params.update({option: value, "local_ipv4_network_cidr": "10.20.0.0/16"})
    client = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode), connection)

    assert raised.value.values == {
        "changed": False,
        "msg": f"Cannot change {option} on an existing VPN connection with this module",
    }
    assert client.mock_calls == []


@pytest.mark.parametrize("returned", [True, False])
def test_create_only_connection_options_matching_the_connection_are_unchanged(params, connection, returned):
    # Live: EC2 returns EnableAcceleration and OutsideIpAddressType even for a connection created without them.
    params.update(enable_acceleration=False, outside_ip_address_type="PublicIpv4")
    if returned:
        connection["Options"].update(EnableAcceleration=False, OutsideIpAddressType="PublicIpv4")

    client = Mock()
    assert ensure(client, FakeModule(params), connection)["changed"] is False
    connection["Options"].update(
        EnableAcceleration=True, OutsideIpAddressType="PrivateIpv4", TransportTransitGatewayAttachmentId="tgw-attach-1"
    )
    params.update(
        enable_acceleration=True,
        outside_ip_address_type="PrivateIpv4",
        transport_transit_gateway_attachment_id="tgw-attach-1",
    )
    assert ensure(client, FakeModule(params), connection)["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize("option", ["transport_transit_gateway_attachment_id", "vpn_concentrator_id"])
@pytest.mark.parametrize("blank", ["", " "])
def test_blank_create_only_ids_fail_before_any_aws_call(params, option, blank):
    # Live: EC2 created a connection without a concentrator or attachment for whitespace-only IDs.
    params[option] = blank
    module = FakeModule(params)
    module.require_botocore_at_least = Mock()
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_inputs(module)

    assert raised.value.values == {"msg": f"{option} must not be empty"}


@pytest.mark.parametrize("existing", [True, False])
def test_concentrator_connections_reject_static_routes(params, connection, existing):
    params.update(customer_gateway_id="cgw-123", static_only=True, routes=["10.20.0.0/16"])
    if existing:
        connection.pop("VpnGatewayId")
        connection["VpnConcentratorId"] = "vcn-123"
    else:
        params["vpn_concentrator_id"] = "vcn-123"

    client = Mock()
    with pytest.raises(ModuleFail, match="virtual private gateway connection"):
        plugin.ensure_present(client, FakeModule(params), connection if existing else None)

    assert client.mock_calls == []


@pytest.mark.parametrize("state", ["present", "absent"])
@pytest.mark.parametrize(
    "option", [None, "log_enabled", "bgp_log_enabled", "bgp_log_group_arn", "bgp_log_output_format"]
)
def test_bgp_log_options_require_botocore_only_when_supplied(params, state, option):
    values = {
        "log_enabled": True,
        "bgp_log_enabled": True,
        "bgp_log_group_arn": LOG_GROUP_ARN,
        "bgp_log_output_format": "text",
    }
    supplied = {option: values[option]} if option else {}
    params.update(state=state, tunnel_options=[{"log_options": {"cloud_watch_log_options": supplied}}])
    module = FakeModule(params)
    module.require_botocore_at_least = Mock(side_effect=ModuleFail({"msg": "botocore"}))
    if state == "present" and option and option.startswith("bgp_"):
        with pytest.raises(ModuleFail, match="botocore"):
            plugin.validate_inputs(module)

        module.require_botocore_at_least.assert_called_once_with("1.41.1", reason=f"for {option}")
    else:
        plugin.validate_inputs(module)
        module.require_botocore_at_least.assert_not_called()


@pytest.mark.parametrize(
    "tunnels, changed",
    [
        ([{"startup_action": "start"}], True),
        ([{"log_options": {"cloud_watch_log_options": {"log_enabled": False}}}], True),
        ([{"log_options": {"cloud_watch_log_options": {}}}], False),
        ([{"log_options": {"cloud_watch_log_options": None}}], False),
    ],
)
def test_pending_vpn_check_mode_predicts_new_tunnel_options(params, connection, tunnels, changed):
    connection["State"] = "pending"
    connection["Options"]["TunnelOptions"] = []
    params.update(skip_tunnel_replacement=True, tunnel_options=tunnels)
    client = Mock()
    assert ensure(client, FakeModule(params, check_mode=True), connection)["changed"] is changed
    assert client.mock_calls == []


def test_documented_returns_cover_connection_and_tunnel_fields():
    returns = documented_returns(plugin)["vpn_connection"]["contains"]
    model = Session().get_service_model("ec2")

    def snake(shape_name, excluded):
        names = [name for name in model.shape_for(shape_name).members if name not in excluded]
        return {plugin.camel_dict_to_snake_dict({name: None}).popitem()[0] for name in names}

    assert snake("VpnConnection", {"CustomerGatewayConfiguration"}) <= set(returns)
    assert_documents_shape(returns["options"]["contains"], "ec2", "VpnConnectionOptions")
    tunnel = returns["options"]["contains"]["tunnel_options"]["contains"]
    assert snake("TunnelOption", {"PreSharedKey"}) <= set(tunnel)
    assert_documents_shape(tunnel["log_options"]["contains"], "ec2", "VpnTunnelLogOptions")
