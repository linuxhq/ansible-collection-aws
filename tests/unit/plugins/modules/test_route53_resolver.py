from unittest.mock import ANY, Mock, patch

import pytest

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


@pytest.mark.parametrize("explicit_first", [False, True])
@pytest.mark.parametrize(
    "field,current_addresses,requested",
    [
        ("Ip", ["10.0.0.10", "10.0.0.11"], "10.0.0.10"),
        ("Ipv6", ["2001:db8::10", "2001:db8::11"], "2001:0DB8:0000:0000:0000:0000:0000:0010"),
    ],
)
def test_mixed_explicit_and_automatic_addresses_match_without_replacement(
    explicit_first, field, current_addresses, requested
):
    client = Mock()
    module = FakeModule({"wait": False})
    endpoint = {
        "Id": "rslvr-endpt-1",
        "IpAddresses": [
            {"SubnetId": "subnet-a", field: current_addresses[0], "IpId": "ip-1"},
            {"SubnetId": "subnet-a", field: current_addresses[1], "IpId": "ip-2"},
        ],
    }
    addresses = [{"subnet_id": "subnet-a"}, {"subnet_id": "subnet-a", field.lower(): requested}]
    if explicit_first:
        addresses.reverse()

    assert plugin.comparable_ip_addresses_match(
        plugin.comparable_ip_addresses(endpoint["IpAddresses"]), plugin.comparable_ip_addresses(addresses)
    )
    with (
        patch.object(plugin, "get_resolver_endpoint", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", return_value=endpoint),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
    ):
        result = plugin.reconcile_resolver_endpoint_ip_addresses(
            client, module, endpoint, {"name": "example", "ip_addresses": addresses}
        )

    assert result == endpoint
    client.associate_resolver_endpoint_ip_address.assert_not_called()
    client.disassociate_resolver_endpoint_ip_address.assert_not_called()
    wait.assert_not_called()


@pytest.mark.parametrize("endpoint_type", ["dualstack", "ipv4", "ipv6"])
def test_explicit_address_pair_uses_real_argument_validation(endpoint_type):
    client = Mock()
    client.create_resolver_endpoint.return_value = {"ResolverEndpoint": {"Id": "rslvr-endpt-1"}}
    arguments = {
        "name": "example",
        "direction": "inbound",
        "resolver_endpoint_type": endpoint_type,
        "security_group_ids": ["sg-example"],
        "wait": False,
        "ip_addresses": [
            {"subnet_id": "subnet-a", "ip": "10.0.0.10", "ipv6": "2001:db8:1::10"},
            {"subnet_id": "subnet-b", "ip": "10.0.1.10", "ipv6": "2001:db8:2::10"},
        ],
    }

    def initialize(**kwargs):
        kwargs.pop("supports_check_mode")
        result = ArgumentSpecValidator(**kwargs).validate(arguments)
        assert not result.error_messages, result.error_messages
        return FakeModule(result.validated_parameters, client=client)

    with (
        patch.object(plugin, "AnsibleAWSModule", side_effect=initialize),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        pytest.raises(ModuleExit if endpoint_type == "dualstack" else ModuleFail) as raised,
    ):
        plugin.main()

    if endpoint_type == "dualstack":
        assert raised.value.values["changed"]
        assert client.create_resolver_endpoint.call_args.kwargs["IpAddresses"] == [
            {"SubnetId": entry["subnet_id"], "Ip": entry["ip"], "Ipv6": entry["ipv6"]}
            for entry in arguments["ip_addresses"]
        ]
    else:
        assert "require resolver_endpoint_type=dualstack" in raised.value.values["msg"]
        client.create_resolver_endpoint.assert_not_called()


def test_get_rejects_malformed_response():
    client = Mock(get_resolver_endpoint=Mock(return_value=[]))
    module = FakeModule({"name": "endpoint"})

    with pytest.raises(ModuleFail) as raised:
        plugin.get_resolver_endpoint(client, module, "rslvr-endpt-1")

    assert raised.value.values["msg"] == "get_resolver_endpoint: AWS returned an invalid resolver endpoint"


def test_get_rejects_unexpected_endpoint_id():
    client = Mock(get_resolver_endpoint=Mock(return_value={"ResolverEndpoint": {"Id": "rslvr-endpt-2"}}))
    module = FakeModule({"name": "endpoint"})

    with pytest.raises(ModuleFail) as raised:
        plugin.get_resolver_endpoint(client, module, "rslvr-endpt-1")

    assert "unexpected resolver endpoint ID" in raised.value.values["msg"]


def test_create_rereads_endpoint_when_response_is_lean():
    client = Mock(create_resolver_endpoint=Mock(return_value={}))
    module = FakeModule({"tags": None, "wait": False})
    desired = {
        "direction": "OUTBOUND",
        "ip_addresses": [{"subnet_id": "subnet-1"}],
        "name": "main",
        "protocols": ["Do53"],
        "resolver_endpoint_type": "IPV4",
        "security_group_ids": ["sg-1"],
    }
    endpoint = {"Id": "rslvr-endpt-1", "Name": "main"}

    with patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint) as get:
        result = plugin.create_resolver_endpoint(client, module, desired)

    get.assert_called_once_with(client, module, changed=True)
    assert result["Id"] == "rslvr-endpt-1"


def test_list_by_name_rejects_malformed_endpoint():
    module = FakeModule({"name": "endpoint"})
    with (
        patch.object(plugin, "query_list", return_value=[{"Name": "endpoint"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_resolver_endpoint_by_name(Mock(), module)

    assert "without a valid ID" in raised.value.values["msg"]


def test_ip_and_tag_enrichment_reject_malformed_entries():
    module = FakeModule({"name": "endpoint"})
    endpoint = {"Arn": "arn:aws:route53resolver:::endpoint", "Id": "rslvr-endpt-1"}

    with (
        patch.object(plugin, "query_list", return_value=[{"Ip": "192.0.2.1"}]),
        pytest.raises(ModuleFail) as ip_raised,
    ):
        plugin.resolver_endpoint_with_ip_addresses(Mock(), module, endpoint)

    assert "without a subnet ID" in ip_raised.value.values["msg"]

    with (
        patch.object(plugin, "query_list", return_value=[{"Key": "Name"}]),
        pytest.raises(ModuleFail) as tag_raised,
    ):
        plugin.resolver_endpoint_with_tags(Mock(), module, endpoint)

    assert "invalid tag" in tag_raised.value.values["msg"]


def test_absent_waits_for_deleting_endpoint_without_deleting_again():
    client = Mock()
    module = FakeModule({"name": "endpoint", "wait": True})
    endpoint = {"Id": "rslvr-endpt-1", "Status": "DELETING"}
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint),
        patch.object(plugin, "delete_resolver_endpoint") as delete,
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert not raised.value.values["changed"]
    delete.assert_not_called()
    wait.assert_called_once_with(client, module, "rslvr-endpt-1", {"deleted"})


def test_delete_waits_when_requested():
    client = Mock()
    module = FakeModule({"name": "endpoint", "wait": True})
    with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
        plugin.delete_resolver_endpoint(client, module, {"Id": "rslvr-endpt-1"})

    wait.assert_called_once_with(client, module, "rslvr-endpt-1", {"deleted"}, changed=True)


def test_delete_tolerates_endpoint_disappearing():
    client = Mock()
    client.delete_resolver_endpoint.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteResolverEndpoint",
    )
    module = FakeModule({"name": "endpoint", "wait": True})
    with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
        plugin.delete_resolver_endpoint(client, module, {"Id": "rslvr-endpt-1"})

    wait.assert_not_called()


def test_module_contract():
    assert_module_contract(plugin)


def test_absent_rejects_invalid_name():
    assert_module_rejects(
        plugin,
        {"name": "", "state": "absent", "tags": None},
        "name must be a valid resolver endpoint name of at most 64 characters",
    )


def test_empty_tags_do_not_gate_tag_resource():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "endpoint",
            "protocols": ["do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "state": "present",
            "tags": {},
            "wait": False,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    methods = require_methods.call_args.args[3]
    assert "tag_resource" not in methods
    assert "untag_resource" in methods


def test_endpoint_list_limits_are_rejected():
    base = {
        "ip_addresses": [
            {"subnet_id": "subnet-1"},
            {"subnet_id": "subnet-2"},
        ],
        "name": "endpoint",
        "protocols": ["Do53"],
        "security_group_ids": ["sg-1"],
        "state": "present",
        "tags": None,
    }
    cases = [
        (
            dict(base, name="123"),
            "name must be a valid resolver endpoint name of at most 64 characters",
        ),
        (
            dict(base, ip_addresses=[{"subnet_id": "subnet-1"}]),
            "ip_addresses must contain 2 to 20 entries",
        ),
        (
            dict(
                base,
                ip_addresses=[
                    {"subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-1"},
                ],
            ),
            "ip_addresses entries must be unique",
        ),
        (dict(base, protocols=[]), "protocols must contain 1 or 2 entries"),
        (
            dict(base, security_group_ids=[]),
            "security_group_ids must contain at least one entry",
        ),
        (
            dict(base, security_group_ids=["s" * 65]),
            "security_group_ids entries must contain 1 to 64 characters",
        ),
        (
            dict(
                base,
                ip_addresses=[
                    {"subnet_id": "s" * 33},
                    {"subnet_id": "subnet-2"},
                ],
            ),
            "ip_addresses[].subnet_id must contain 1 to 32 characters",
        ),
        (
            dict(
                base,
                ip_addresses=[
                    {"ip": "2001:db8::1", "subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
            ),
            "ip_addresses[].ip must be a valid IPv4 address",
        ),
        (
            dict(
                base,
                ip_addresses=[
                    {"ipv6": "192.0.2.1", "subnet_id": "subnet-1"},
                    {"subnet_id": "subnet-2"},
                ],
            ),
            "ip_addresses[].ipv6 must be a valid IPv6 address",
        ),
        (
            dict(base, tags={str(index): "" for index in range(201)}),
            "tags must contain at most 200 entries",
        ),
    ]
    for params, message in cases:
        assert_module_rejects(plugin, params, message)


def test_endpoint_comparison_ignores_order_and_response_fields():
    endpoint = {
        "Direction": "OUTBOUND",
        "IpAddresses": [
            {"SubnetId": "subnet-b", "IpId": "rni-2"},
            {"SubnetId": "subnet-a", "Ip": "192.0.2.1", "Status": "ATTACHED"},
        ],
        "Protocols": ["DoH", "Do53", "DoH"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-b", "sg-a", "sg-b"],
        "Status": "OPERATIONAL",
    }
    assert plugin.comparable_endpoint(endpoint) == {
        "direction": "OUTBOUND",
        "ip_addresses": [
            {"ip": "192.0.2.1", "subnet_id": "subnet-a"},
            {"subnet_id": "subnet-b"},
        ],
        "protocols": ["Do53", "DoH"],
        "resolver_endpoint_type": "IPV4",
        "security_group_ids": ["sg-a", "sg-b"],
    }


def test_endpoint_settings_have_no_module_defaults():
    options = assert_module_contract(plugin)
    assert "default" not in options["argument_spec"]["protocols"]
    assert "default" not in options["argument_spec"]["resolver_endpoint_type"]


def test_omitted_protocols_and_type_leave_an_existing_endpoint_unchanged():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
                {"ip": "192.0.2.2", "subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": None,
            "purge_tags": True,
            "resolver_endpoint_type": None,
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"Ip": "192.0.2.1", "SubnetId": "subnet-1"},
            {"Ip": "192.0.2.2", "SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53", "DoH"],
        "ResolverEndpointType": "DUALSTACK",
        "SecurityGroupIds": ["sg-1"],
    }
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    assert raised.value.values["resolver_endpoint"]["protocols"] == ["Do53", "DoH"]
    client.update_resolver_endpoint.assert_not_called()


def test_check_mode_predicts_aws_defaults_for_a_new_endpoint():
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
            "name": "main",
            "protocols": None,
            "purge_tags": True,
            "resolver_endpoint_type": None,
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    endpoint = raised.value.values["resolver_endpoint"]
    assert endpoint["protocols"] == ["Do53"]
    assert endpoint["resolver_endpoint_type"] == "IPV4"


def test_auto_assigned_ip_addresses_are_idempotent():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"Ip": "192.0.2.1", "SubnetId": "subnet-1"},
            {"Ip": "192.0.2.2", "SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(
            plugin,
            "resolver_endpoint_with_ip_addresses",
            side_effect=lambda *args, **kwargs: args[2],
        ),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    client.associate_resolver_endpoint_ip_address.assert_not_called()
    client.disassociate_resolver_endpoint_ip_address.assert_not_called()


def test_check_mode_preserves_unchanged_auto_assigned_addresses():
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["doh"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        },
        check_mode=True,
    )
    current = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"Ip": "192.0.2.1", "SubnetId": "subnet-1"},
            {"Ip": "192.0.2.2", "SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(
            plugin,
            "resolver_endpoint_with_ip_addresses",
            side_effect=lambda *args, **kwargs: args[2],
        ),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert raised.value.values["changed"]
    assert raised.value.values["resolver_endpoint"]["ip_addresses"] == [
        {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
        {"ip": "192.0.2.2", "subnet_id": "subnet-2"},
    ]


def test_create_token_changes_with_desired_endpoint():
    client = Mock(
        create_resolver_endpoint=Mock(
            side_effect=[
                {"ResolverEndpoint": {"Id": "endpoint-1"}},
                {"ResolverEndpoint": {"Id": "endpoint-2"}},
            ]
        )
    )
    module = FakeModule({"tags": None, "wait": False})
    desired = {
        "direction": "OUTBOUND",
        "ip_addresses": [{"subnet_id": "subnet-1"}],
        "name": "main",
        "protocols": ["Do53"],
        "resolver_endpoint_type": "IPV4",
        "security_group_ids": ["sg-1"],
    }
    created = plugin.create_resolver_endpoint(client, module, desired)
    plugin.create_resolver_endpoint(client, module, dict(desired, direction="INBOUND"))

    tokens = [call.kwargs["CreatorRequestId"] for call in client.create_resolver_endpoint.call_args_list]
    assert tokens[0] != tokens[1]
    assert created["IpAddresses"] == [{"SubnetId": "subnet-1"}]


def test_ip_reconciliation_adds_and_removes_only_differences():
    client = Mock()
    module = Mock(params={"wait": False})
    endpoint = {
        "Id": "rslvr-1",
        "IpAddresses": [{"IpId": "rni-old", "SubnetId": "subnet-old"}],
    }
    desired = {
        "name": "main",
        "ip_addresses": [{"subnet_id": "subnet-new"}],
    }
    with (
        patch.object(
            plugin,
            "wait_for_resolver_endpoint_status",
        ) as wait_for_resolver_endpoint_status,
    ):
        result = plugin.reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired)

    client.associate_resolver_endpoint_ip_address.assert_called_once_with(
        IpAddress={"SubnetId": "subnet-new"},
        ResolverEndpointId="rslvr-1",
        aws_retry=True,
    )
    client.disassociate_resolver_endpoint_ip_address.assert_called_once_with(
        IpAddress={"IpId": "rni-old", "SubnetId": "subnet-old"},
        ResolverEndpointId="rslvr-1",
        aws_retry=True,
    )
    wait_for_resolver_endpoint_status.assert_called_once_with(client, module, "rslvr-1", {"settled"}, changed=True)
    assert result["Id"] == "rslvr-1"
    assert result["IpAddresses"] == [{"SubnetId": "subnet-new"}]


def test_ip_replacements_stay_within_provider_count_bounds():
    for count, first_operation in ((2, "associate"), (20, "disassociate")):
        current = [{"IpId": f"rni-{index}", "SubnetId": f"subnet-{index}"} for index in range(count)]
        desired = {
            "name": "main",
            "ip_addresses": [{"subnet_id": f"subnet-{index}"} for index in range(1, count)]
            + [{"subnet_id": "subnet-new"}],
        }
        client = Mock()
        with (patch.object(plugin, "wait_for_resolver_endpoint_status"),):
            plugin.reconcile_resolver_endpoint_ip_addresses(
                client,
                Mock(params={"wait": False}),
                {"Id": "rslvr-1", "IpAddresses": current},
                desired,
            )

        assert client.method_calls[0][0].startswith(first_operation)


def test_direction_change_preserves_the_endpoint():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "Direction": "INBOUND",
        "Id": "rslvr-old",
        "IpAddresses": [
            {"SubnetId": "subnet-1"},
            {"SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(
            plugin,
            "resolver_endpoint_with_ip_addresses",
            side_effect=lambda *args, **kwargs: args[2],
        ),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(
            plugin,
            "reconcile_resolver_endpoint_ip_addresses",
            return_value=current,
        ),
        patch.object(plugin, "delete_resolver_endpoint") as delete,
        patch.object(plugin, "create_resolver_endpoint") as create,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert "direction cannot be changed" in raised.value.values["msg"]
    delete.assert_not_called()
    create.assert_not_called()
    client.update_resolver_endpoint.assert_not_called()


def test_no_wait_change_waits_for_operational_endpoint_and_rechecks():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        }
    )
    transitioning = {
        "Direction": "INBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"SubnetId": "subnet-1"},
            {"SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
        "Status": "UPDATING",
    }
    active = dict(transitioning, Direction="OUTBOUND", Status="OPERATIONAL")
    with (
        patch.object(
            plugin,
            "get_resolver_endpoint_by_name",
            side_effect=[transitioning, active],
        ),
        patch.object(
            plugin,
            "resolver_endpoint_with_ip_addresses",
            side_effect=lambda *args, **kwargs: args[2],
        ),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait_for_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait_for_status.assert_called_once_with(client, module, "rslvr-1", {"settled"})
    client.update_resolver_endpoint.assert_not_called()
    assert not raised.value.values["changed"]


def test_waited_endpoint_is_enriched_before_ip_reconciliation():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["doh"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": True,
        }
    )
    current = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"SubnetId": "subnet-1"},
            {"SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    updated = dict(current, Protocols=["DoH"])
    waited = {key: value for key, value in updated.items() if key != "IpAddresses"}
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": updated}
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=waited),
        patch.object(
            plugin,
            "resolver_endpoint_with_ip_addresses",
            side_effect=[current, updated],
        ) as enrich,
        patch.object(
            plugin,
            "reconcile_resolver_endpoint_ip_addresses",
            return_value=updated,
        ) as reconcile,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    enrich.assert_called_with(client, module, waited, changed=True)
    reconcile.assert_called_once_with(client, module, updated, ANY, changed=True)


def test_update_rereads_endpoint_when_response_is_lean():
    client = Mock(update_resolver_endpoint=Mock(return_value={}))
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["doh"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"SubnetId": "subnet-1"},
            {"SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    updated = dict(current, Protocols=["DoH"])
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(plugin, "get_resolver_endpoint", return_value=updated) as get,
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "reconcile_resolver_endpoint_ip_addresses", return_value=updated),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    get.assert_called_once_with(client, module, "rslvr-1", changed=True)


def test_tag_change_rejects_endpoint_without_arn():
    client = Mock()
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": {"Name": "main"},
            "wait": False,
        }
    )
    current = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"SubnetId": "subnet-1"},
            {"SubnetId": "subnet-2"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert "invalid endpoint ARN" in raised.value.values["msg"]
    client.tag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("field,value", [("direction", "inbound"), ("security_group_ids", ["sg-2"])])
def test_immutable_changes_never_mutate_endpoint(check_mode, field, value):
    params = {
        "direction": "outbound",
        "ip_addresses": [{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
        "name": "main",
        "protocols": ["do53"],
        "purge_tags": True,
        "resolver_endpoint_type": "ipv4",
        "security_group_ids": ["sg-1"],
        "tags": None,
        "wait": True,
    }
    endpoint = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [{"SubnetId": "subnet-1"}, {"SubnetId": "subnet-2"}],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    params[field] = value
    module = FakeModule(params, check_mode=check_mode)
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_tags", return_value=endpoint),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert field in raised.value.values["msg"]
    assert client.mock_calls == []


@pytest.mark.parametrize("wait", [False, True])
def test_unresolved_update_never_replaces_endpoint(wait):
    module = FakeModule(
        {
            "direction": "outbound",
            "ip_addresses": [{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
            "name": "main",
            "protocols": ["doh"],
            "purge_tags": True,
            "resolver_endpoint_type": "ipv4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": wait,
        }
    )
    endpoint = {
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [{"SubnetId": "subnet-1"}, {"SubnetId": "subnet-2"}],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
    }
    client = Mock()
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": endpoint}
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_tags", return_value=endpoint),
        patch.object(plugin, "validate_resolver_endpoint", return_value=endpoint),
        patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=endpoint),
        patch.object(plugin, "reconcile_resolver_endpoint_ip_addresses", return_value=endpoint),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["current"]["protocols"] == ["Do53"]
    assert raised.value.values["desired"]["protocols"] == ["DoH"]
    client.delete_resolver_endpoint.assert_not_called()
    client.create_resolver_endpoint.assert_not_called()
    client.update_resolver_endpoint.assert_called_once_with(
        ResolverEndpointId="rslvr-1", Protocols=["DoH"], aws_retry=True
    )


def endpoint_params(**overrides):
    params = {
        "direction": "outbound",
        "ip_addresses": [
            {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
            {"ip": "192.0.2.2", "subnet_id": "subnet-2"},
        ],
        "name": "main",
        "protocols": None,
        "purge_tags": True,
        "resolver_endpoint_type": None,
        "security_group_ids": ["sg-1"],
        "tags": None,
        "wait": False,
        "wait_delay": 5,
        "wait_timeout": 300,
    }
    params.update(overrides)
    return params


def existing_endpoint(**overrides):
    endpoint = {
        "Arn": "arn:endpoint",
        "Direction": "OUTBOUND",
        "Id": "rslvr-1",
        "IpAddresses": [
            {"Ip": "192.0.2.1", "IpId": "rni-1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            {"Ip": "192.0.2.2", "IpId": "rni-2", "SubnetId": "subnet-2", "Status": "ATTACHED"},
        ],
        "Protocols": ["Do53"],
        "ResolverEndpointType": "IPV4",
        "SecurityGroupIds": ["sg-1"],
        "Status": "OPERATIONAL",
        "Tags": [],
    }
    endpoint.update(overrides)
    return endpoint


def acceptor_states(waiter_name):
    model = plugin.ROUTE53_RESOLVER_ENDPOINT_WAITER_MODEL_DATA[waiter_name]
    return {acceptor["expected"]: acceptor["state"] for acceptor in model["acceptors"]}


def test_waiting_for_a_usable_endpoint_stops_when_it_is_deleting():
    assert acceptor_states("resolver_endpoint_operational")["DELETING"] == "failure"
    assert acceptor_states("resolver_endpoint_settled") == {
        "OPERATIONAL": "success",
        "ACTION_NEEDED": "success",
        "DELETING": "failure",
        "CREATING": "retry",
        "UPDATING": "retry",
        "AUTO_RECOVERING": "retry",
    }
    # Waiting for deletion still waits through DELETING until the endpoint is gone.
    assert acceptor_states("resolver_endpoint_deleted") == {
        "ResourceNotFoundException": "success",
        "DELETING": "retry",
    }


def test_wait_failure_message_does_not_claim_a_timeout():
    module = FakeModule(endpoint_params())
    with patch.object(plugin, "run_waiter") as run_waiter, patch.object(plugin, "get_resolver_endpoint"):
        plugin.wait_for_resolver_endpoint_status(Mock(), module, "rslvr-1", {"operational"})

    assert run_waiter.call_args.args[3] == "resolver_endpoint_operational"
    assert run_waiter.call_args.args[4] == "Unable to wait for AWS Route53 Resolver endpoint main to become operational"


def test_failed_addresses_are_replaced_and_departing_addresses_are_ignored():
    client = Mock()
    module = FakeModule(endpoint_params())
    endpoint = existing_endpoint(
        IpAddresses=[
            {"Ip": "192.0.2.1", "IpId": "rni-1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            {"Ip": "192.0.2.2", "IpId": "rni-2", "SubnetId": "subnet-2", "Status": "FAILED_RESOURCE_GONE"},
            {"Ip": "192.0.2.9", "IpId": "rni-9", "SubnetId": "subnet-2", "Status": "DELETING"},
        ]
    )
    desired = {"name": "main", "ip_addresses": plugin.comparable_ip_addresses(endpoint_params()["ip_addresses"])}
    with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
        plugin.reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired)

    client.associate_resolver_endpoint_ip_address.assert_called_once_with(
        IpAddress={"Ip": "192.0.2.2", "SubnetId": "subnet-2"}, ResolverEndpointId="rslvr-1", aws_retry=True
    )
    client.disassociate_resolver_endpoint_ip_address.assert_called_once_with(
        IpAddress={"Ip": "192.0.2.2", "IpId": "rni-2", "SubnetId": "subnet-2"},
        ResolverEndpointId="rslvr-1",
        aws_retry=True,
    )
    wait.assert_called_once_with(client, module, "rslvr-1", {"settled"}, changed=True)


def test_failed_address_makes_an_existing_endpoint_differ():
    endpoint = existing_endpoint(
        IpAddresses=[
            {"Ip": "192.0.2.1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            {"Ip": "192.0.2.2", "SubnetId": "subnet-2", "Status": "FAILED_CREATION"},
        ]
    )
    desired = plugin.comparable_endpoint(
        {
            "direction": "OUTBOUND",
            "ip_addresses": endpoint_params()["ip_addresses"],
            "protocols": ["Do53"],
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
        }
    )
    assert not plugin.comparable_endpoints_match(plugin.comparable_endpoint(endpoint), desired)


def test_unchanged_addresses_do_not_reread_the_endpoint():
    client = Mock()
    module = FakeModule(endpoint_params(wait=True))
    endpoint = existing_endpoint()
    desired = {"name": "main", "ip_addresses": plugin.comparable_ip_addresses(endpoint_params()["ip_addresses"])}
    with (
        patch.object(plugin, "get_resolver_endpoint") as get,
        patch.object(plugin, "resolver_endpoint_with_ip_addresses") as with_ip_addresses,
    ):
        assert plugin.reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired) is endpoint

    get.assert_not_called()
    with_ip_addresses.assert_not_called()
    assert client.mock_calls == []


def test_get_resolver_endpoint_does_not_list_tags():
    client = Mock(get_resolver_endpoint=Mock(return_value={"ResolverEndpoint": existing_endpoint()}))
    with patch.object(plugin, "resolver_endpoint_with_tags") as with_tags:
        plugin.get_resolver_endpoint(client, FakeModule(endpoint_params()), "rslvr-1")

    with_tags.assert_not_called()


def test_dual_stack_conversion_sends_requested_ipv6_addresses():
    client = Mock()
    client.update_resolver_endpoint.return_value = {
        "ResolverEndpoint": existing_endpoint(ResolverEndpointType="DUALSTACK", Status="UPDATING")
    }
    params = endpoint_params(
        resolver_endpoint_type="dualstack",
        ip_addresses=[
            {"ip": "192.0.2.1", "ipv6": "2001:db8::1", "subnet_id": "subnet-1"},
            {"ip": "192.0.2.2", "ipv6": "2001:db8::2", "subnet_id": "subnet-2"},
        ],
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(
            plugin,
            "wait_for_resolver_endpoint_status",
            return_value=existing_endpoint(ResolverEndpointType="DUALSTACK"),
        ),
        patch.object(plugin, "reconcile_resolver_endpoint_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "comparable_endpoints_match", side_effect=[False, True]),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, FakeModule(params))

    client.update_resolver_endpoint.assert_called_once_with(
        ResolverEndpointId="rslvr-1",
        ResolverEndpointType="DUALSTACK",
        UpdateIpAddresses=[{"IpId": "rni-1", "Ipv6": "2001:db8::1"}, {"IpId": "rni-2", "Ipv6": "2001:db8::2"}],
        aws_retry=True,
    )


@pytest.mark.parametrize(
    "overrides, current_overrides, message_part",
    [
        ({"resolver_endpoint_type": "ipv6"}, {}, "resolver_endpoint_type to or from ipv6"),
        (
            {"resolver_endpoint_type": "ipv4"},
            {"ResolverEndpointType": "IPV6"},
            "resolver_endpoint_type to or from ipv6",
        ),
        (
            {"direction": "inbound", "protocols": ["doh"]},
            {"Direction": "INBOUND"},
            "directly from do53 to doh on an inbound endpoint",
        ),
        (
            {"direction": "inbound", "protocols": ["doh-fips"]},
            {"Direction": "INBOUND"},
            "Add the new protocol alongside do53 first",
        ),
    ],
)
def test_changes_aws_does_not_support_fail_before_modifying(overrides, current_overrides, message_part):
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint(**current_overrides)),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleFail) as result,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(**overrides)))

    assert message_part in result.value.values["msg"]
    client.update_resolver_endpoint.assert_not_called()


@pytest.mark.parametrize(
    "current_protocols, requested_protocols, expected_protocols",
    [
        (["Do53"], ["do53", "doh"], ["Do53", "DoH"]),
        (["Do53", "DoH"], ["doh"], ["DoH"]),
        (["DoH"], ["do53"], ["Do53"]),
    ],
)
def test_inbound_endpoint_protocols_are_updated(current_protocols, requested_protocols, expected_protocols):
    client = Mock()
    updated = existing_endpoint(Direction="INBOUND", Protocols=expected_protocols)
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": updated}
    with (
        patch.object(
            plugin,
            "get_resolver_endpoint_by_name",
            return_value=existing_endpoint(Direction="INBOUND", Protocols=current_protocols),
        ),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(direction="inbound", protocols=requested_protocols)))

    assert raised.value.values["changed"]
    assert raised.value.values["resolver_endpoint"]["protocols"] == expected_protocols
    client.update_resolver_endpoint.assert_called_once_with(
        ResolverEndpointId="rslvr-1",
        Protocols=expected_protocols,
        aws_retry=True,
    )
    wait.assert_not_called()


def test_no_wait_update_with_matching_subnet_only_addresses_does_not_wait():
    client = Mock()
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": existing_endpoint(Protocols=["DoH"])}
    params = endpoint_params(
        ip_addresses=[{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
        protocols=["doh"],
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert raised.value.values["changed"]
    wait.assert_not_called()
    client.associate_resolver_endpoint_ip_address.assert_not_called()
    client.disassociate_resolver_endpoint_ip_address.assert_not_called()


def test_endpoint_needing_action_fails_with_the_aws_status_message():
    endpoint = existing_endpoint(Status="ACTION_NEEDED", StatusMessage="Subnet subnet-2 has no free addresses")
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleFail) as result,
    ):
        plugin.ensure_present(Mock(), FakeModule(endpoint_params(wait=True)))

    wait.assert_not_called()
    assert result.value.values["msg"] == (
        "AWS Route53 Resolver endpoint main needs action: Subnet subnet-2 has no free addresses"
    )


def test_delete_rejected_by_aws_names_the_likely_dependency():
    client = Mock()
    client.delete_resolver_endpoint.side_effect = plugin.ClientError(
        {"Error": {"Code": "InvalidRequestException", "Message": "in use"}}, "DeleteResolverEndpoint"
    )
    with pytest.raises(ModuleFail) as result:
        plugin.delete_resolver_endpoint(client, FakeModule(endpoint_params()), existing_endpoint())

    assert result.value.values["msg"] == (
        "Unable to delete AWS Route53 Resolver endpoint main; "
        "if resolver rules still use it, delete or update those rules first"
    )


def test_update_reuses_tags_read_at_the_start():
    client = Mock()
    # UpdateResolverEndpoint responses do not include tags.
    updated = existing_endpoint(Protocols=["Do53", "DoH"])
    updated.pop("Tags")
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": updated}
    start = existing_endpoint(Tags=[{"Key": "Name", "Value": "main"}])
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=start),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]) as with_tags,
        patch.object(plugin, "reconcile_resolver_endpoint_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(protocols=["do53", "doh"], tags={"Name": "main"})))

    assert with_tags.call_count == 1
    assert result.value.values["resolver_endpoint"]["tags"] == {"Name": "main"}
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


def failing_waiter(module, client, model_data, waiter_name, error_msg, changed=False, **kwargs):
    module.fail_json(changed=changed, msg=error_msg)


def endpoint_with_failed_address():
    return existing_endpoint(
        IpAddresses=[
            {"Ip": "192.0.2.1", "IpId": "rni-1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            {"Ip": "192.0.2.2", "IpId": "rni-2", "SubnetId": "subnet-2", "Status": "ATTACHED"},
            {"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3", "Status": "FAILED_CREATION"},
        ],
        Status="ACTION_NEEDED",
    )


def test_failed_address_dropped_from_the_request_is_removed():
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint_with_failed_address()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params()))

    assert raised.value.values["changed"] is True
    client.disassociate_resolver_endpoint_ip_address.assert_called_once_with(
        IpAddress={"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3"},
        ResolverEndpointId="rslvr-1",
        aws_retry=True,
    )
    client.associate_resolver_endpoint_ip_address.assert_not_called()
    client.update_resolver_endpoint.assert_not_called()
    wait.assert_not_called()


def test_check_mode_predicts_removing_a_failed_address_dropped_from_the_request():
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint_with_failed_address()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(), check_mode=True))

    assert raised.value.values["changed"] is True
    assert [ip_address["ip"] for ip_address in raised.value.values["resolver_endpoint"]["ip_addresses"]] == [
        "192.0.2.1",
        "192.0.2.2",
    ]
    assert client.mock_calls == []


def test_create_wait_failure_reports_changed():
    client = Mock(create_resolver_endpoint=Mock(return_value={"ResolverEndpoint": existing_endpoint()}))
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to wait for AWS Route53 Resolver endpoint main to become operational"


def test_delete_wait_failure_reports_changed():
    with (
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.delete_resolver_endpoint(Mock(), FakeModule(endpoint_params(wait=True)), existing_endpoint())

    assert raised.value.values["changed"] is True


def test_endpoint_that_needs_action_after_an_update_reports_changed():
    client = Mock()
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": existing_endpoint(Status="UPDATING")}
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(
            plugin,
            "wait_for_resolver_endpoint_status",
            return_value=existing_endpoint(Protocols=["DoH"], Status="ACTION_NEEDED"),
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(protocols=["doh"], wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"].startswith("AWS Route53 Resolver endpoint main needs action")


@pytest.mark.parametrize(("protocols", "changed"), [(["do53", "doh"], True), (None, False)])
def test_tag_failure_reports_whether_the_endpoint_was_updated(protocols, changed):
    client = Mock()
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": existing_endpoint(Protocols=["Do53", "DoH"])}
    client.tag_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServiceErrorException", "Message": "failed"}}, "TagResource"
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_endpoint_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "reconcile_resolver_endpoint_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(protocols=protocols, tags={"Env": "test"})))

    assert raised.value.values["msg"] == "Unable to tag AWS Route53 Resolver endpoint arn:endpoint"
    assert raised.value.values["changed"] is changed
    assert client.update_resolver_endpoint.called is changed


def failing_query(module, client, method_name, result_key, error_msg, changed=False, **kwargs):
    module.fail_json(changed=changed, msg=error_msg)


def test_address_listing_failure_after_create_reports_changed():
    client = Mock(create_resolver_endpoint=Mock(return_value={"ResolverEndpoint": existing_endpoint()}))
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        patch.object(plugin, "run_waiter"),
        patch.object(plugin, "get_resolver_endpoint", return_value=existing_endpoint()),
        patch.object(plugin, "query_list", side_effect=failing_query),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to list AWS Route53 Resolver endpoint IP addresses for rslvr-1"


def test_lookup_failure_before_create_reports_unchanged():
    client = Mock()
    with (
        patch.object(plugin, "query_list", side_effect=failing_query),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params()))

    assert raised.value.values["changed"] is False
    client.create_resolver_endpoint.assert_not_called()
