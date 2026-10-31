from unittest.mock import ANY, Mock, patch

import pytest
from botocore.session import get_session

from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

from ansible_collections.amazon.aws.plugins.module_utils.retries import RetryingBotoClientWrapper

from ansible_collections.linuxhq.aws.plugins.module_utils import route53_resolver as route53_resolver_utils
from ansible_collections.linuxhq.aws.plugins.module_utils import wait as wait_utils
from ansible_collections.linuxhq.aws.plugins.modules import route53_resolver as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    assert_documents_shape,
    assert_module_contract,
    assert_module_rejects,
    documented_returns,
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

    assert plugin.comparable_ips_match(
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


@pytest.mark.parametrize("endpoint_type", ["DUALSTACK", "IPV4", "IPV6"])
def test_explicit_address_pair_uses_real_argument_validation(endpoint_type):
    client = Mock()
    client.create_resolver_endpoint.return_value = {"ResolverEndpoint": {"Id": "rslvr-endpt-1"}}
    arguments = {
        "name": "example",
        "direction": "INBOUND",
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
        pytest.raises(ModuleExit if endpoint_type == "DUALSTACK" else ModuleFail) as raised,
    ):
        plugin.main()

    if endpoint_type == "DUALSTACK":
        assert raised.value.values["changed"]
        assert client.create_resolver_endpoint.call_args.kwargs["IpAddresses"] == [
            {"SubnetId": entry["subnet_id"], "Ip": entry["ip"], "Ipv6": entry["ipv6"]}
            for entry in arguments["ip_addresses"]
        ]
    else:
        assert "require resolver_endpoint_type=DUALSTACK" in raised.value.values["msg"]
        client.create_resolver_endpoint.assert_not_called()


def test_enum_choices_match_the_sdk_model():
    spec = assert_module_contract(plugin)["argument_spec"]
    model = get_session().get_service_model("route53resolver")

    assert sorted(spec["direction"]["choices"]) == sorted(model.shape_for("ResolverEndpointDirection").enum)
    assert sorted(spec["protocols"]["choices"]) == sorted(model.shape_for("Protocol").enum)
    assert sorted(spec["resolver_endpoint_type"]["choices"]) == sorted(model.shape_for("ResolverEndpointType").enum)


@pytest.mark.parametrize(
    "overrides",
    [
        {"direction": "inbound"},
        {"protocols": ["do53"]},
        {"protocols": ["doh-fips"]},
        {"resolver_endpoint_type": "dualstack"},
    ],
)
def test_lowercase_enum_values_are_rejected(overrides):
    spec = assert_module_contract(plugin)
    spec.pop("supports_check_mode")
    arguments = dict(
        {
            "direction": "INBOUND",
            "ip_addresses": [{"subnet_id": "subnet-a"}, {"subnet_id": "subnet-b"}],
            "name": "example",
            "security_group_ids": ["sg-example"],
        },
        **overrides,
    )

    result = ArgumentSpecValidator(**spec).validate(arguments)

    assert any("value of" in message for message in result.error_messages)


@pytest.mark.parametrize("direction", ["INBOUND", "INBOUND_DELEGATION", "OUTBOUND"])
def test_provider_enum_values_are_sent_unchanged(direction):
    client = Mock()
    client.create_resolver_endpoint.return_value = {"ResolverEndpoint": {"Id": "rslvr-endpt-1", "Name": "main"}}
    module = FakeModule(
        endpoint_params(direction=direction, protocols=["DoH", "Do53"], resolver_endpoint_type="DUALSTACK"),
        client=client,
    )

    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    request = client.create_resolver_endpoint.call_args.kwargs
    assert request["Direction"] == direction
    assert request["Protocols"] == ["Do53", "DoH"]
    assert request["ResolverEndpointType"] == "DUALSTACK"
    assert raised.value.values["changed"]


@pytest.mark.parametrize("direction", ["INBOUND_DELEGATION", "OUTBOUND"])
def test_direction_values_are_not_gated_on_botocore(direction):
    module = FakeModule(endpoint_params(direction=direction, state="present"))
    module.require_botocore_at_least = Mock(side_effect=ModuleFail({"msg": "botocore"}))

    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", side_effect=ModuleExit({})),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    module.require_botocore_at_least.assert_not_called()


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
        patch.object(route53_resolver_utils, "query_list", return_value=[{"Key": "Name"}]),
        pytest.raises(ModuleFail) as tag_raised,
    ):
        plugin.resolver_resource_with_tags(Mock(), module, endpoint, "endpoint")

    assert "invalid tag" in tag_raised.value.values["msg"]


def test_absent_waits_for_deleting_endpoint_without_deleting_again():
    client = Mock()
    module = FakeModule({"name": "endpoint", "wait": True, "wait_timeout": 300})
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
    wait.assert_called_once_with(client, module, "rslvr-endpt-1", "deleted", deadline=ANY)


def test_delete_waits_when_requested():
    client = Mock()
    module = FakeModule({"name": "endpoint", "wait": True, "wait_timeout": 300})
    with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
        plugin.delete_resolver_endpoint(client, module, {"Id": "rslvr-endpt-1"})

    wait.assert_called_once_with(client, module, "rslvr-endpt-1", "deleted", changed=True, deadline=ANY)


def test_delete_tolerates_endpoint_disappearing():
    client = Mock()
    client.delete_resolver_endpoint.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteResolverEndpoint",
    )
    module = FakeModule({"name": "endpoint", "wait": True})
    with patch.object(plugin, "wait_for_resolver_endpoint_status") as wait:
        assert plugin.delete_resolver_endpoint(client, module, {"Id": "rslvr-endpt-1"}) is False

    wait.assert_not_called()


def test_absent_reports_unchanged_when_endpoint_is_already_gone():
    client = Mock()
    client.delete_resolver_endpoint.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteResolverEndpoint",
    )
    module = FakeModule({"name": "endpoint", "wait": True, "wait_timeout": 300})
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value={"Id": "rslvr-endpt-1"}),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    wait.assert_not_called()


def test_module_contract():
    assert_module_contract(plugin)


def test_documented_returns_cover_the_sdk_shapes():
    contains = documented_returns(plugin)["resolver_endpoint"]["contains"]
    assert_documents_shape(contains, "route53resolver", "ResolverEndpoint")
    assert_documents_shape(contains["ip_addresses"]["contains"], "route53resolver", "IpAddressResponse")


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
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "endpoint",
            "protocols": ["Do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
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
                    {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
                    {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
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


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("blank", ["", " "])
@pytest.mark.parametrize(
    "option,message",
    [
        ("security_group_ids", "security_group_ids entries must contain 1 to 64 characters"),
        ("subnet_id", "ip_addresses[].subnet_id must contain 1 to 32 characters"),
    ],
)
def test_blank_identifiers_are_rejected_before_any_aws_call(check_mode, blank, option, message):
    # Live: AWS reads a whitespace-only security group or subnet ID as empty and refuses it.
    ip_addresses = [
        {"ip": "192.0.2.1", "ipv6": None, "subnet_id": "subnet-1"},
        {"ip": None, "ipv6": None, "subnet_id": blank if option == "subnet_id" else "subnet-2"},
    ]
    security_group_ids = ["sg-1", blank] if option == "security_group_ids" else ["sg-1"]
    module = FakeModule(
        endpoint_params(ip_addresses=ip_addresses, security_group_ids=security_group_ids, state="present"),
        check_mode=check_mode,
    )
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "ensure_present") as ensure_present,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": message}
    module.client.assert_not_called()
    ensure_present.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_blank_subnet_is_rejected_before_an_existing_endpoint_gains_an_address(check_mode):
    # Live: a real run added the explicit address first and only then had "Subnet ID cannot be empty" refused, so it
    # failed with changed=true and an extra address, while check mode predicted success.
    client = Mock()
    module = FakeModule(
        endpoint_params(
            ip_addresses=[
                {"ip": "192.0.2.11", "ipv6": None, "subnet_id": "subnet-1"},
                {"ip": None, "ipv6": None, "subnet_id": " "},
            ],
            state="present",
        ),
        check_mode=check_mode,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=existing_endpoint()),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": "ip_addresses[].subnet_id must contain 1 to 32 characters"}
    assert client.mock_calls == []


def test_subnet_only_entries_may_share_a_subnet():
    module = FakeModule(
        endpoint_params(
            ip_addresses=[{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-1"}],
            state="present",
        )
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


def test_subnet_only_entries_match_endpoint_addresses_in_one_subnet():
    current = plugin.comparable_ip_addresses([{"SubnetId": "subnet-1"}, {"SubnetId": "subnet-1", "Ip": "192.0.2.1"}])
    desired = plugin.comparable_ip_addresses([{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-1"}])

    assert plugin.comparable_ips_match(current, desired)
    assert not plugin.comparable_ips_match(current[:1], desired)


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
            "direction": "OUTBOUND",
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
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    assert raised.value.values["resolver_endpoint"]["protocols"] == ["Do53", "DoH"]
    client.update_resolver_endpoint.assert_not_called()


def test_check_mode_predicts_aws_defaults_for_a_new_endpoint():
    module = FakeModule(
        {
            "direction": "OUTBOUND",
            "ip_addresses": [{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
            "name": "main",
            "protocols": None,
            "purge_tags": True,
            "resolver_endpoint_type": None,
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
            "wait_timeout": 300,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(model_client(), module)

    endpoint = raised.value.values["resolver_endpoint"]
    assert endpoint["protocols"] == ["Do53"]
    assert endpoint["resolver_endpoint_type"] == "IPV4"


def test_auto_assigned_ip_addresses_are_idempotent():
    client = Mock()
    module = FakeModule(
        {
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["Do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    client.associate_resolver_endpoint_ip_address.assert_not_called()
    client.disassociate_resolver_endpoint_ip_address.assert_not_called()


def test_check_mode_preserves_unchanged_auto_assigned_addresses():
    module = FakeModule(
        {
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["DoH"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert raised.value.values["changed"]
    assert raised.value.values["resolver_endpoint"]["ip_addresses"] == [
        {"ip": "192.0.2.1", "subnet_id": "subnet-1"},
        {"ip": "192.0.2.2", "subnet_id": "subnet-2"},
    ]


def test_create_token_is_unique_per_create():
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
    plugin.create_resolver_endpoint(client, module, desired)

    tokens = [call.kwargs["CreatorRequestId"] for call in client.create_resolver_endpoint.call_args_list]
    assert tokens[0] != tokens[1]
    assert created["IpAddresses"] == [{"SubnetId": "subnet-1"}]


def test_create_retries_reuse_the_creator_request_id():
    raw_client = Mock()
    raw_client.create_resolver_endpoint.side_effect = [
        plugin.ClientError({"Error": {"Code": "Throttling", "Message": "slow down"}}, "CreateResolverEndpoint"),
        {"ResolverEndpoint": {"Id": "endpoint-1"}},
    ]
    client = RetryingBotoClientWrapper(raw_client, plugin.AWSRetry.jittered_backoff(delay=0))
    module = FakeModule({"tags": None, "wait": False})
    plugin.create_resolver_endpoint(
        client,
        module,
        {
            "direction": "OUTBOUND",
            "ip_addresses": [{"subnet_id": "subnet-1"}],
            "name": "main",
            "protocols": ["Do53"],
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
        },
    )

    first, second = raw_client.create_resolver_endpoint.call_args_list
    assert first.kwargs["CreatorRequestId"]
    assert first.kwargs["CreatorRequestId"] == second.kwargs["CreatorRequestId"]


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
    wait_for_resolver_endpoint_status.assert_called_once_with(
        client, module, "rslvr-1", "settled", changed=True, deadline=ANY
    )
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
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["Do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["Do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait_for_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait_for_status.assert_called_once_with(client, module, "rslvr-1", "settled", deadline=ANY)
    client.update_resolver_endpoint.assert_not_called()
    assert not raised.value.values["changed"]


def test_waited_endpoint_is_enriched_before_ip_reconciliation():
    client = Mock()
    module = FakeModule(
        {
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["DoH"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": True,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
    reconcile.assert_called_once_with(client, module, updated, ANY, changed=True, deadline=ANY)


def test_update_rereads_endpoint_when_response_is_lean():
    client = Mock(update_resolver_endpoint=Mock(return_value={}))
    module = FakeModule(
        {
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["DoH"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": False,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
            "direction": "OUTBOUND",
            "ip_addresses": [
                {"subnet_id": "subnet-1"},
                {"subnet_id": "subnet-2"},
            ],
            "name": "main",
            "protocols": ["Do53"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": {"Name": "main"},
            "wait": False,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert "invalid endpoint ARN" in raised.value.values["msg"]
    client.tag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("field,value", [("direction", "INBOUND"), ("security_group_ids", ["sg-2"])])
def test_immutable_changes_never_mutate_endpoint(check_mode, field, value):
    params = {
        "direction": "OUTBOUND",
        "ip_addresses": [{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
        "name": "main",
        "protocols": ["Do53"],
        "purge_tags": True,
        "resolver_endpoint_type": "IPV4",
        "security_group_ids": ["sg-1"],
        "tags": None,
        "wait": True,
        "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", return_value=endpoint),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert field in raised.value.values["msg"]
    assert client.mock_calls == []


@pytest.mark.parametrize("wait", [False, True])
def test_unresolved_update_never_replaces_endpoint(wait):
    module = FakeModule(
        {
            "direction": "OUTBOUND",
            "ip_addresses": [{"subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}],
            "name": "main",
            "protocols": ["DoH"],
            "purge_tags": True,
            "resolver_endpoint_type": "IPV4",
            "security_group_ids": ["sg-1"],
            "tags": None,
            "wait": wait,
            "wait_timeout": 300,
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
        patch.object(plugin, "resolver_resource_with_tags", return_value=endpoint),
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
        "direction": "OUTBOUND",
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


def in_flight_endpoint(**overrides):
    """Return the endpoint as an IP address change response returns it (live: UPDATING, no addresses or tags)."""
    endpoint = existing_endpoint(StatusMessage="Updating the Resolver Endpoint", Status="UPDATING", **overrides)
    del endpoint["IpAddresses"], endpoint["Tags"]
    return endpoint


IP_ADDRESS_STATUS_CLASSES = {
    "ATTACHED": "kept",
    "ATTACHING": "kept",
    "CREATING": "kept",
    "DELETE_FAILED_FAS_EXPIRED": "kept",
    "DELETING": "departing",
    "DETACHING": "departing",
    "FAILED_CREATION": "failed",
    "FAILED_CREATION_INSUFFICIENT_EC2_CAPACITY_IN_OUTPOST": "failed",
    "FAILED_RESOURCE_GONE": "failed",
    "ISOLATED": "kept",
    "REMAP_ATTACHING": "kept",
    "REMAP_DETACHING": "kept",
    "UPDATE_FAILED": "kept",
    "UPDATING": "kept",
}


def test_every_sdk_ip_address_status_is_classified():
    model = get_session().get_service_model("route53resolver")

    assert set(IP_ADDRESS_STATUS_CLASSES) == set(model.shape_for("IpAddressStatus").enum)


@pytest.mark.parametrize("status", sorted(IP_ADDRESS_STATUS_CLASSES))
def test_ip_address_status_classification(status):
    ip_address = {"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3", "Status": status}
    expected = IP_ADDRESS_STATUS_CLASSES[status]

    assert (status in plugin.FAILED_IP_ADDRESS_STATUSES) is (expected == "failed")
    assert (status in plugin.DEPARTING_IP_ADDRESS_STATUSES) is (expected == "departing")
    assert (plugin.usable_ip_addresses([ip_address]) == [ip_address]) is (expected == "kept")


@pytest.mark.parametrize("status", ["DELETE_FAILED_FAS_EXPIRED", "ISOLATED", "REMAP_DETACHING", "UPDATE_FAILED"])
def test_kept_address_satisfies_its_request_without_replacement(status):
    client = Mock()
    endpoint = existing_endpoint(
        IpAddresses=[
            {"Ip": "192.0.2.1", "IpId": "rni-1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            {"Ip": "192.0.2.2", "IpId": "rni-2", "SubnetId": "subnet-2", "Status": status},
        ]
    )
    desired = {"name": "main", "ip_addresses": plugin.comparable_ip_addresses(endpoint_params()["ip_addresses"])}
    module = FakeModule(endpoint_params())

    assert plugin.reconcile_resolver_endpoint_ip_addresses(client, module, endpoint, desired) is endpoint
    assert client.mock_calls == []


@pytest.mark.parametrize("status", ["DELETE_FAILED_FAS_EXPIRED", "UPDATE_FAILED"])
def test_unwanted_kept_address_is_disassociated_again(status):
    client = Mock()
    endpoint = existing_endpoint(
        IpAddresses=[
            {"Ip": "192.0.2.1", "IpId": "rni-1", "SubnetId": "subnet-1", "Status": "ATTACHED"},
            {"Ip": "192.0.2.2", "IpId": "rni-2", "SubnetId": "subnet-2", "Status": "ATTACHED"},
            {"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3", "Status": status},
        ]
    )
    desired = {"name": "main", "ip_addresses": plugin.comparable_ip_addresses(endpoint_params()["ip_addresses"])}
    with patch.object(plugin, "wait_for_resolver_endpoint_status"):
        plugin.reconcile_resolver_endpoint_ip_addresses(client, FakeModule(endpoint_params()), endpoint, desired)

    client.associate_resolver_endpoint_ip_address.assert_not_called()
    client.disassociate_resolver_endpoint_ip_address.assert_called_once_with(
        IpAddress={"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3"},
        ResolverEndpointId="rslvr-1",
        aws_retry=True,
    )


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
    with (
        patch.object(plugin, "custom_waiter") as custom_waiter,
        patch.object(plugin, "run_waiter") as run_waiter,
        patch.object(plugin, "get_resolver_endpoint"),
    ):
        plugin.wait_for_resolver_endpoint_status(Mock(), module, "rslvr-1", "operational")

    assert custom_waiter.call_args.args[2] == "resolver_endpoint_operational"
    assert run_waiter.call_args.args[2] == "Unable to wait for AWS Route53 Resolver endpoint main to become operational"


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
    wait.assert_called_once_with(client, module, "rslvr-1", "settled", changed=True, deadline=ANY)


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
    with patch.object(plugin, "resolver_resource_with_tags") as with_tags:
        plugin.get_resolver_endpoint(client, FakeModule(endpoint_params()), "rslvr-1")

    with_tags.assert_not_called()


def test_dual_stack_conversion_sends_requested_ipv6_addresses():
    client = Mock()
    client.update_resolver_endpoint.return_value = {
        "ResolverEndpoint": existing_endpoint(ResolverEndpointType="DUALSTACK", Status="UPDATING")
    }
    params = endpoint_params(
        resolver_endpoint_type="DUALSTACK",
        ip_addresses=[
            {"ip": "192.0.2.1", "ipv6": "2001:db8::1", "subnet_id": "subnet-1"},
            {"ip": "192.0.2.2", "ipv6": "2001:db8::2", "subnet_id": "subnet-2"},
        ],
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
        ({"resolver_endpoint_type": "IPV6"}, {}, "resolver_endpoint_type to or from IPV6"),
        (
            {"resolver_endpoint_type": "IPV4"},
            {"ResolverEndpointType": "IPV6"},
            "resolver_endpoint_type to or from IPV6",
        ),
        (
            {"direction": "INBOUND", "protocols": ["DoH"]},
            {"Direction": "INBOUND"},
            "directly from Do53 to DoH on an INBOUND endpoint",
        ),
        (
            {"direction": "INBOUND", "protocols": ["DoH-FIPS"]},
            {"Direction": "INBOUND"},
            "Add the new protocol alongside Do53 first",
        ),
    ],
)
def test_changes_aws_does_not_support_fail_before_modifying(overrides, current_overrides, message_part):
    client = Mock()
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint(**current_overrides)),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleFail) as result,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(**overrides)))

    assert message_part in result.value.values["msg"]
    client.update_resolver_endpoint.assert_not_called()


@pytest.mark.parametrize(
    "current_protocols, requested_protocols, expected_protocols",
    [
        (["Do53"], ["Do53", "DoH"], ["Do53", "DoH"]),
        (["Do53", "DoH"], ["DoH"], ["DoH"]),
        (["DoH"], ["Do53"], ["Do53"]),
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(direction="INBOUND", protocols=requested_protocols)))

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
        protocols=["DoH"],
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]) as with_tags,
        patch.object(plugin, "reconcile_resolver_endpoint_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(protocols=["Do53", "DoH"], tags={"Name": "main"})))

    assert with_tags.call_count == 1
    assert result.value.values["resolver_endpoint"]["tags"] == {"Name": "main"}
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


def failing_waiter(module, waiter, error_msg, changed=False, **kwargs):
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(), check_mode=True))

    assert raised.value.values["changed"] is True
    assert [ip_address["ip"] for ip_address in raised.value.values["resolver_endpoint"]["ip_addresses"]] == [
        "192.0.2.1",
        "192.0.2.2",
    ]
    assert client.mock_calls == []


@pytest.mark.parametrize(
    ("wait", "expected"),
    [
        # Without a wait, a real run returns the requested addresses after removing the failed one.
        (False, [{"ip": "192.0.2.1", "subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}]),
        # A waited run lists the remaining addresses again.
        (
            True,
            [
                {"ip": "192.0.2.1", "ip_id": "rni-1", "status": "ATTACHED", "subnet_id": "subnet-1"},
                {"ip": "192.0.2.2", "ip_id": "rni-2", "status": "ATTACHED", "subnet_id": "subnet-2"},
            ],
        ),
    ],
)
def test_removing_a_failed_address_predicts_the_addresses_a_real_run_returns(wait, expected):
    params = endpoint_params(ip_addresses=[{"ip": "192.0.2.1", "subnet_id": "subnet-1"}, {"subnet_id": "subnet-2"}])
    results = {}
    for check_mode in (False, True):
        client = Mock()
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint_with_failed_address()),
            patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=existing_endpoint()),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, FakeModule(dict(params, wait=wait), check_mode=check_mode))

        results[check_mode] = raised.value.values
        if check_mode:
            assert client.mock_calls == []
        else:
            client.disassociate_resolver_endpoint_ip_address.assert_called_once_with(
                IpAddress={"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3"},
                ResolverEndpointId="rslvr-1",
                aws_retry=True,
            )

    for values in results.values():
        assert values["changed"] is True
        assert values["resolver_endpoint"]["ip_addresses"] == expected


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("wait", "expected_status"),
    [
        # Live, AssociateResolverEndpointIpAddress returns the endpoint UPDATING and already counting the address.
        (False, "UPDATING"),
        # A waited run gets the endpoint again once it is OPERATIONAL.
        (True, "OPERATIONAL"),
    ],
)
def test_added_address_returns_the_status_and_count_a_real_run_returns(check_mode, wait, expected_status):
    added = {"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-3", "Status": "ATTACHED"}
    waited = existing_endpoint(IpAddressCount=3)
    del waited["IpAddresses"], waited["Tags"]
    client = Mock()
    client.associate_resolver_endpoint_ip_address.return_value = {
        "ResolverEndpoint": in_flight_endpoint(IpAddressCount=3)
    }

    def with_ip_addresses(client, module, endpoint, changed=False):
        ip_addresses = existing_endpoint()["IpAddresses"]
        if endpoint["IpAddressCount"] == 3:
            ip_addresses.append(added)

        return dict(endpoint, IpAddresses=ip_addresses)

    ip_addresses = endpoint_params()["ip_addresses"] + [{"ip": "192.0.2.3", "subnet_id": "subnet-3"}]
    module = FakeModule(endpoint_params(ip_addresses=ip_addresses, wait=wait), check_mode=check_mode)
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint(IpAddressCount=2)),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=with_ip_addresses),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=waited),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["resolver_endpoint"]["ip_address_count"] == 3
    assert raised.value.values["resolver_endpoint"]["status"] == expected_status
    if check_mode:
        assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [False, True])
def test_replaced_failed_address_returns_the_count_a_waited_run_rereads(check_mode):
    listed = dict(endpoint_with_failed_address(), IpAddressCount=3)
    waited = existing_endpoint(IpAddressCount=2)
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=listed),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=waited),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), FakeModule(endpoint_params(wait=True), check_mode=check_mode))

    assert raised.value.values["changed"] is True
    assert raised.value.values["resolver_endpoint"]["ip_address_count"] == 2


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("wait", "extra_address", "status"),
    [
        # Live, UpdateResolverEndpoint returns the endpoint UPDATING with the new protocols.
        (False, False, "UPDATING"),
        # Address changes that follow an update wait for the endpoint to settle first; live, the unwaited address
        # change then returns the endpoint UPDATING again.
        (False, True, "UPDATING"),
        (True, False, "OPERATIONAL"),
    ],
)
def test_protocol_update_predicts_the_status_a_real_run_returns(check_mode, wait, extra_address, status):
    client = Mock()
    client.update_resolver_endpoint.return_value = {
        "ResolverEndpoint": existing_endpoint(Protocols=["Do53", "DoH"], Status="UPDATING")
    }
    client.associate_resolver_endpoint_ip_address.return_value = {
        "ResolverEndpoint": in_flight_endpoint(IpAddressCount=3, Protocols=["Do53", "DoH"])
    }
    ip_addresses = endpoint_params()["ip_addresses"]
    if extra_address:
        ip_addresses = ip_addresses + [{"ip": "192.0.2.3", "subnet_id": "subnet-3"}]

    module = FakeModule(
        endpoint_params(ip_addresses=ip_addresses, protocols=["Do53", "DoH"], wait=wait), check_mode=check_mode
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(
            plugin, "wait_for_resolver_endpoint_status", return_value=existing_endpoint(Protocols=["Do53", "DoH"])
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["resolver_endpoint"]["protocols"] == ["Do53", "DoH"]
    assert raised.value.values["resolver_endpoint"]["status"] == status
    if check_mode:
        assert client.mock_calls == []
    else:
        client.update_resolver_endpoint.assert_called_once()
        assert client.associate_resolver_endpoint_ip_address.call_count == (1 if extra_address else 0)


def test_create_wait_failure_reports_changed():
    client = Mock(create_resolver_endpoint=Mock(return_value={"ResolverEndpoint": existing_endpoint()}))
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        patch.object(plugin, "custom_waiter"),
        patch.object(plugin, "run_waiter", side_effect=failing_waiter),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to wait for AWS Route53 Resolver endpoint main to become operational"


def test_delete_wait_failure_reports_changed():
    with (
        patch.object(plugin, "custom_waiter"),
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
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(
            plugin,
            "wait_for_resolver_endpoint_status",
            return_value=existing_endpoint(Protocols=["DoH"], Status="ACTION_NEEDED"),
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(protocols=["DoH"], wait=True)))

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"].startswith("AWS Route53 Resolver endpoint main needs action")


@pytest.mark.parametrize(("protocols", "changed"), [(["Do53", "DoH"], True), (None, False)])
def test_tag_failure_reports_whether_the_endpoint_was_updated(protocols, changed):
    client = Mock()
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": existing_endpoint(Protocols=["Do53", "DoH"])}
    client.tag_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServiceErrorException", "Message": "failed"}}, "TagResource"
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
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
        patch.object(plugin, "custom_waiter"),
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


@pytest.mark.parametrize("check_mode", [False, True])
def test_resulting_tag_limit_fails_before_updating_the_endpoint(check_mode):
    client = Mock()
    existing_tags = [{"Key": "aws:reserved", "Value": ""}]
    existing_tags += [{"Key": f"old{index}", "Value": ""} for index in range(200)]
    params = endpoint_params(
        ip_addresses=[{"ip": "192.0.2.3", "subnet_id": "subnet-3"}, {"ip": "192.0.2.2", "subnet_id": "subnet-2"}],
        purge_tags=False,
        tags={"new": ""},
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint(Tags=existing_tags)),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(
            plugin, "reconcile_resolver_endpoint_ip_addresses", side_effect=lambda *args, **kwargs: args[2]
        ) as reconcile,
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_resolver_endpoint_status", side_effect=lambda *args, **kwargs: args[2]) as wait,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values["msg"] == (
        "The resulting AWS Route53 Resolver endpoint tags must contain at most 200 entries"
    )
    assert raised.value.values.get("changed", False) is False
    reconcile.assert_not_called()
    wait.assert_not_called()
    client.update_resolver_endpoint.assert_not_called()
    client.tag_resource.assert_not_called()


def waiter_configs(waiter):
    """Return the WaiterConfig that reached each wait, for comparing with the expected remaining budgets."""
    return [wait_call.kwargs["WaiterConfig"] for wait_call in waiter.wait.call_args_list]


def budget_configs(*timeouts):
    return [wait_utils.custom_waiter_config(timeout, default_pause=5) for timeout in timeouts]


def sdk_error():
    return plugin.ClientError({"Error": {"Code": "Failed", "Message": "no"}}, "Wait")


def test_waits_after_a_re_run_share_one_wait_timeout_budget():
    waiter = Mock()
    waiter.wait.side_effect = [None, sdk_error()]
    with (
        patch.object(
            plugin,
            "get_resolver_endpoint_by_name",
            return_value={"Id": "rslvr-1", "Name": "main", "Status": "DELETING"},
        ),
        patch.object(plugin, "custom_waiter", return_value=waiter),
        patch.object(wait_utils.time, "monotonic", side_effect=[100, 100, 700]),
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_present(Mock(), FakeModule(endpoint_params(wait_timeout=1800)))

    assert waiter_configs(waiter) == budget_configs(1800, 1200)


def test_an_exhausted_wait_timeout_budget_fails_with_the_timeout_message():
    waiter = Mock()
    with (
        patch.object(
            plugin,
            "get_resolver_endpoint_by_name",
            return_value={"Id": "rslvr-1", "Name": "main", "Status": "DELETING"},
        ),
        patch.object(plugin, "custom_waiter", return_value=waiter),
        patch.object(wait_utils.time, "monotonic", side_effect=[100, 100, 1901]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), FakeModule(endpoint_params(wait_timeout=1800)))

    waiter.wait.assert_called_once()
    assert raised.value.values == {
        "changed": False,
        "msg": "Unable to wait for AWS Route53 Resolver endpoint main to become deleted",
    }


def test_ip_address_changes_wait_only_for_the_remaining_budget():
    endpoint = {"Id": "rslvr-1", "IpAddresses": [{"IpId": "rni-old", "SubnetId": "subnet-old"}]}
    desired = {"name": "main", "ip_addresses": [{"subnet_id": "subnet-new"}]}
    waiter = Mock()
    with (
        patch.object(plugin, "custom_waiter", return_value=waiter),
        patch.object(plugin, "get_resolver_endpoint", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", return_value=endpoint),
        patch.object(wait_utils.time, "monotonic", side_effect=[400, 1000]),
    ):
        plugin.reconcile_resolver_endpoint_ip_addresses(
            Mock(), FakeModule(endpoint_params(wait=True, wait_timeout=1800)), endpoint, desired, deadline=1900
        )

    assert waiter_configs(waiter) == budget_configs(1500, 900)


def test_ip_address_changes_with_wait_get_the_endpoint_once():
    endpoint = {"Id": "rslvr-1", "IpAddresses": [{"IpId": "rni-old", "SubnetId": "subnet-old"}]}
    desired = {"name": "main", "ip_addresses": [{"subnet_id": "subnet-old"}, {"subnet_id": "subnet-new"}]}
    waited = {"Id": "rslvr-1", "Status": "OPERATIONAL"}
    client = Mock()
    client.get_resolver_endpoint.return_value = {"ResolverEndpoint": waited}
    with (
        patch.object(plugin, "custom_waiter"),
        patch.object(plugin, "run_waiter"),
        patch.object(
            plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]
        ) as enrich,
    ):
        result = plugin.reconcile_resolver_endpoint_ip_addresses(
            client, FakeModule(endpoint_params(wait=True)), endpoint, desired
        )

    assert result == waited
    client.associate_resolver_endpoint_ip_address.assert_called_once()
    assert client.get_resolver_endpoint.call_count == 1
    enrich.assert_called_once_with(client, ANY, waited, changed=True)


@pytest.mark.parametrize("check_mode", [False, True])
def test_tag_only_change_returns_the_stored_security_groups_and_protocols(check_mode):
    client = Mock()
    endpoint = existing_endpoint(Protocols=["DoH", "Do53"], SecurityGroupIds=["sg-b", "sg-a"])
    module = FakeModule(
        endpoint_params(protocols=["DoH", "Do53"], security_group_ids=["sg-b", "sg-a"], tags={"Env": "test"}),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    result = raised.value.values
    assert result["changed"] is True
    assert result["resolver_endpoint"]["security_group_ids"] == ["sg-b", "sg-a"]
    assert result["resolver_endpoint"]["protocols"] == ["DoH", "Do53"]
    assert result["resolver_endpoint"]["tags"] == {"Env": "test"}
    client.update_resolver_endpoint.assert_not_called()


def test_check_mode_protocol_change_keeps_the_stored_security_groups():
    client = Mock()
    endpoint = existing_endpoint(SecurityGroupIds=["sg-b", "sg-a"])
    module = FakeModule(
        endpoint_params(protocols=["DoH", "Do53"], security_group_ids=["sg-b", "sg-a"]),
        check_mode=True,
    )
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=endpoint),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    result = raised.value.values
    assert result["changed"] is True
    assert result["resolver_endpoint"]["protocols"] == ["Do53", "DoH"]
    assert result["resolver_endpoint"]["security_group_ids"] == ["sg-b", "sg-a"]
    client.update_resolver_endpoint.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("wait", [False, True])
def test_create_without_tags_returns_tags_only_when_waiting(check_mode, wait):
    created = existing_endpoint()
    created.pop("Tags")
    module = FakeModule(endpoint_params(wait=wait), check_mode=check_mode)
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "create_resolver_endpoint", return_value=created) as create,
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(route53_resolver_utils, "query_list", return_value=[]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(model_client(), module)

    assert raised.value.values["changed"] is True
    assert create.call_count == (0 if check_mode else 1)
    endpoint = raised.value.values["resolver_endpoint"]
    if wait:
        assert endpoint["tags"] == {}
    else:
        assert "tags" not in endpoint


def model_client():
    """Return a mock client with the real botocore route53resolver model, for predictions that read it."""
    return Mock(meta=get_session().create_client("route53resolver", region_name="us-east-1").meta)


# Live CreateResolverEndpoint and GetResolverEndpoint responses return these settings for a new endpoint.
LIVE_CREATED_ENDPOINT_SETTINGS = {
    "INBOUND": {"Dns64Enabled": False, "RniEnhancedMetricsEnabled": False},
    "INBOUND_DELEGATION": {"Dns64Enabled": False, "RniEnhancedMetricsEnabled": False},
    "OUTBOUND": {
        "Ipv6InternetAccessEnabled": False,
        "RniEnhancedMetricsEnabled": False,
        "TargetNameServerMetricsEnabled": False,
    },
}


def created_endpoint_settings(client, check_mode, **params):
    """Run a create and return the *_enabled settings of the resulting endpoint."""
    direction = params.get("direction", "OUTBOUND")
    created = dict(
        existing_endpoint(Direction=direction, Status="CREATING"), **LIVE_CREATED_ENDPOINT_SETTINGS[direction]
    )
    created.pop("Tags")
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
        patch.object(plugin, "create_resolver_endpoint", return_value=created) as create,
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: dict(args[2], Tags=[])),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(endpoint_params(**params), check_mode=check_mode))

    assert raised.value.values["changed"] is True
    assert create.call_count == (0 if check_mode else 1)
    endpoint = raised.value.values["resolver_endpoint"]
    return {field: value for field, value in endpoint.items() if field.endswith("_enabled")}


@pytest.mark.parametrize("wait", [False, True])
@pytest.mark.parametrize("direction", ["INBOUND", "INBOUND_DELEGATION", "OUTBOUND"])
def test_check_mode_create_predicts_the_settings_a_real_run_returns(direction, wait):
    predicted = created_endpoint_settings(model_client(), True, direction=direction, wait=wait)

    assert predicted
    assert predicted == created_endpoint_settings(model_client(), False, direction=direction, wait=wait)


def test_check_mode_create_predicts_only_settings_the_installed_model_returns():
    # botocore drops response members that its model does not define.
    client = Mock()
    client.meta.service_model.shape_for.return_value.members = {"Id": Mock(), "RniEnhancedMetricsEnabled": Mock()}

    assert created_endpoint_settings(client, True) == {"rni_enhanced_metrics_enabled": False}
    client.meta.service_model.shape_for.assert_called_once_with("ResolverEndpoint")


@pytest.mark.parametrize("wait", [False, True])
def test_conversion_to_ipv4_predicts_the_addresses_a_real_run_returns(wait):
    dual_stack_addresses = [
        dict(ip_address, Ipv6=f"2001:db8::{index}")
        for index, ip_address in enumerate(existing_endpoint()["IpAddresses"], start=1)
    ]

    def with_ip_addresses(client, module, endpoint, changed=False):
        # Live, the addresses keep their IPv6 addresses until a conversion to IPV4 settles.
        ip_addresses = existing_endpoint()["IpAddresses"]
        if endpoint["ResolverEndpointType"] == "DUALSTACK" or endpoint["Status"] == "UPDATING":
            ip_addresses = dual_stack_addresses

        return dict(endpoint, IpAddresses=ip_addresses)

    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.update_resolver_endpoint.return_value = {"ResolverEndpoint": existing_endpoint(Status="UPDATING")}
        module = FakeModule(endpoint_params(resolver_endpoint_type="IPV4", wait=wait), check_mode=check_mode)
        with (
            patch.object(
                plugin,
                "get_resolver_endpoint_by_name",
                return_value=existing_endpoint(ResolverEndpointType="DUALSTACK"),
            ),
            patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=with_ip_addresses),
            patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=existing_endpoint()),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        results[check_mode] = raised.value.values
        if check_mode:
            assert client.mock_calls == []
        else:
            client.update_resolver_endpoint.assert_called_once_with(
                ResolverEndpointId="rslvr-1", ResolverEndpointType="IPV4", aws_retry=True
            )

    for values in results.values():
        assert values["changed"] is True
        assert values["resolver_endpoint"]["resolver_endpoint_type"] == "IPV4"

    predicted = results[True]["resolver_endpoint"]["ip_addresses"]
    assert predicted == results[False]["resolver_endpoint"]["ip_addresses"]
    assert all(("ipv6" in ip_address) is not wait for ip_address in predicted)


def test_replacement_at_the_address_quota_fails_before_removing_an_address():
    current = [
        {"Ip": f"192.0.2.{index}", "IpId": f"rni-{index}", "SubnetId": "subnet-1", "Status": "ATTACHED"}
        for index in range(1, 7)
    ]
    desired = {
        "name": "main",
        "ip_addresses": [{"ip": f"192.0.2.{index}", "subnet_id": "subnet-1"} for index in (1, 2, 3, 4, 5, 7)],
    }
    client = Mock()
    # Live, an endpoint at the default quota of 6 addresses refuses a seventh; additions run before removals.
    client.associate_resolver_endpoint_ip_address.side_effect = plugin.ClientError(
        {
            "Error": {
                "Code": "LimitExceededException",
                "Message": "[RSLVR-00309] Account '123456789012' has exceeded 'max-enis-per-resolver-endpoint'.",
            }
        },
        "AssociateResolverEndpointIpAddress",
    )
    with (
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.reconcile_resolver_endpoint_ip_addresses(
            client, FakeModule(endpoint_params()), {"Id": "rslvr-1", "IpAddresses": current}, desired
        )

    assert raised.value.values == {
        "changed": False,
        "msg": "Unable to reconcile AWS Route53 Resolver endpoint IP addresses for main",
    }
    client.associate_resolver_endpoint_ip_address.assert_called_once()
    client.disassociate_resolver_endpoint_ip_address.assert_not_called()
    wait.assert_not_called()


@pytest.mark.parametrize("status", sorted(plugin.DEPARTING_IP_ADDRESS_STATUSES))
def test_settled_endpoint_prediction_drops_departing_addresses(status):
    # Live, an unwaited removal leaves the endpoint UPDATING, listing and counting the departing address.
    departing = {"Ip": "192.0.2.3", "IpId": "rni-3", "SubnetId": "subnet-2", "Status": status}
    updating = existing_endpoint(
        IpAddressCount=3, IpAddresses=existing_endpoint()["IpAddresses"] + [departing], Status="UPDATING"
    )
    settled = existing_endpoint(IpAddressCount=2)
    results = {}
    for check_mode in (False, True):
        client = Mock()
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", side_effect=[updating, settled]),
            patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=settled) as wait,
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, FakeModule(endpoint_params(wait=True), check_mode=check_mode))

        results[check_mode] = raised.value.values
        assert wait.call_count == (0 if check_mode else 1)
        assert client.mock_calls == []

    assert results[True] == results[False]
    assert results[True]["changed"] is False
    assert results[True]["resolver_endpoint"]["ip_address_count"] == 2
    assert len(results[True]["resolver_endpoint"]["ip_addresses"]) == 2


def test_settled_endpoint_prediction_drops_ipv6_addresses_after_a_conversion_to_ipv4():
    # Live, an unwaited conversion to IPV4 lists the addresses UPDATING with their IPv6 addresses until it settles.
    converting = existing_endpoint(
        IpAddresses=[
            dict(ip_address, Ipv6=f"2001:db8::{index}", Status="UPDATING")
            for index, ip_address in enumerate(existing_endpoint()["IpAddresses"], start=1)
        ],
        Status="UPDATING",
    )
    results = {}
    for check_mode in (False, True):
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", side_effect=[converting, existing_endpoint()]),
            patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=existing_endpoint()),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), FakeModule(endpoint_params(wait=True), check_mode=check_mode))

        assert raised.value.values["changed"] is False
        results[check_mode] = raised.value.values["resolver_endpoint"]

    def addresses_without_status(endpoint):
        # Per-address statuses of an endpoint that is still changing are not predicted.
        return [
            {field: value for field, value in ip_address.items() if field != "status"}
            for ip_address in endpoint["ip_addresses"]
        ]

    predicted = addresses_without_status(results[True])
    assert predicted == addresses_without_status(results[False])
    assert all("ipv6" not in ip_address for ip_address in predicted)
    assert results[True]["status"] == results[False]["status"] == "OPERATIONAL"


@pytest.mark.parametrize("wait", [False, True])
def test_check_mode_create_predicts_the_status_and_address_count_a_real_run_returns(wait):
    # Live, CreateResolverEndpoint returns the endpoint CREATING and counting every requested address, and a
    # waited create returns it OPERATIONAL with the same count.
    ip_addresses = [
        {"ip": None, "ipv6": None, "subnet_id": "subnet-1"},
        {"ip": None, "ipv6": None, "subnet_id": "subnet-1"},
        {"ip": "192.0.2.3", "ipv6": None, "subnet_id": "subnet-2"},
    ]
    created = existing_endpoint(IpAddressCount=3, Status="CREATING")
    for field in ("IpAddresses", "Tags"):
        created.pop(field)

    results = {}
    for check_mode in (False, True):
        client = model_client()
        client.create_resolver_endpoint.return_value = {"ResolverEndpoint": created}
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=None),
            patch.object(
                plugin, "wait_for_resolver_endpoint_status", return_value=dict(created, Status="OPERATIONAL")
            ) as wait_for_status,
            patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(
                plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: dict(args[2], Tags=[])
            ),
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(
                client, FakeModule(endpoint_params(ip_addresses=ip_addresses, wait=wait), check_mode=check_mode)
            )

        assert raised.value.values["changed"] is True
        assert client.create_resolver_endpoint.call_count == (0 if check_mode else 1)
        assert wait_for_status.call_count == (1 if wait and not check_mode else 0)
        results[check_mode] = raised.value.values["resolver_endpoint"]

    for field, expected in (("ip_address_count", 3), ("status", "OPERATIONAL" if wait else "CREATING")):
        assert results[True][field] == results[False][field] == expected


@pytest.mark.parametrize(
    ("current_ips", "requested_ips", "operations"),
    [
        # Live, AssociateResolverEndpointIpAddress returns UPDATING and counts the new address at once.
        (["192.0.2.1", "192.0.2.2"], ["192.0.2.1", "192.0.2.2", "192.0.2.3"], ["add"]),
        # Live, DisassociateResolverEndpointIpAddress returns UPDATING and counts the address until it is gone.
        (["192.0.2.1", "192.0.2.2", "192.0.2.3"], ["192.0.2.1", "192.0.2.2"], ["remove"]),
        # A replacement adds first, waits for the endpoint to settle, and returns the removal's response.
        (["192.0.2.1", "192.0.2.2"], ["192.0.2.1", "192.0.2.3"], ["add", "remove"]),
    ],
    ids=["add", "remove", "replace"],
)
def test_unwaited_address_change_returns_the_last_change_response(current_ips, requested_ips, operations):
    current = existing_endpoint(
        IpAddressCount=len(current_ips),
        IpAddresses=[
            {"Ip": ip, "IpId": f"rni-{ip[-1]}", "SubnetId": f"subnet-{ip[-1]}", "Status": "ATTACHED"}
            for ip in current_ips
        ],
        StatusMessage="This Resolver Endpoint is operational.",
    )
    params = endpoint_params(ip_addresses=[{"ip": ip, "subnet_id": f"subnet-{ip[-1]}"} for ip in requested_ips])
    results = {}
    for check_mode in (False, True):
        client = Mock()
        client.associate_resolver_endpoint_ip_address.return_value = {
            "ResolverEndpoint": in_flight_endpoint(IpAddressCount=len(current_ips) + 1)
        }
        client.disassociate_resolver_endpoint_ip_address.return_value = {
            "ResolverEndpoint": in_flight_endpoint(IpAddressCount=len(current_ips) + operations.count("add"))
        }
        with (
            patch.object(plugin, "get_resolver_endpoint_by_name", return_value=current),
            patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
            patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=current) as wait_for_status,
            pytest.raises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

        assert raised.value.values["changed"] is True
        results[check_mode] = raised.value.values["resolver_endpoint"]
        if check_mode:
            assert client.mock_calls == []
        else:
            assert client.associate_resolver_endpoint_ip_address.call_count == operations.count("add")
            assert client.disassociate_resolver_endpoint_ip_address.call_count == operations.count("remove")
            assert wait_for_status.call_count == len(operations) - 1
            assert results[False]["status_message"] == "Updating the Resolver Endpoint"

    expected_count = len(requested_ips) + (1 if operations[-1] == "remove" else 0)
    for field, expected in (("ip_address_count", expected_count), ("status", "UPDATING")):
        assert results[True][field] == results[False][field] == expected

    assert results[True]["ip_addresses"] == results[False]["ip_addresses"]


def test_unwaited_address_change_with_a_lean_response_keeps_the_endpoint_read_before_it():
    client = Mock()
    client.associate_resolver_endpoint_ip_address.return_value = {}
    params = endpoint_params(ip_addresses=endpoint_params()["ip_addresses"] + [{"ip": "192.0.2.3", "subnet_id": "s"}])
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint(IpAddressCount=2)),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status") as wait_for_status,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    endpoint = raised.value.values["resolver_endpoint"]
    assert (endpoint["status"], endpoint["ip_address_count"], len(endpoint["ip_addresses"])) == ("OPERATIONAL", 2, 3)
    client.associate_resolver_endpoint_ip_address.assert_called_once()
    wait_for_status.assert_not_called()


def test_unwaited_address_change_rejects_a_response_for_another_endpoint():
    client = Mock()
    client.associate_resolver_endpoint_ip_address.return_value = {"ResolverEndpoint": in_flight_endpoint(Id="rslvr-2")}
    params = endpoint_params(ip_addresses=endpoint_params()["ip_addresses"] + [{"ip": "192.0.2.3", "subnet_id": "s"}])
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint()),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert raised.value.values == {
        "changed": True,
        "msg": "associate_resolver_endpoint_ip_address: AWS returned an unexpected resolver endpoint ID rslvr-2",
    }


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("extra_address", "status", "count"),
    [
        # The conversion gives both addresses their requested IPv6 addresses, so no address change follows.
        (False, "OPERATIONAL", 2),
        # Only the extra address is added after the conversion.
        (True, "UPDATING", 3),
    ],
)
def test_unwaited_conversion_to_dual_stack_predicts_the_address_changes_after_it(
    check_mode, extra_address, status, count
):
    requested = [
        {"ip": "192.0.2.1", "ipv6": "2001:db8::1", "subnet_id": "subnet-1"},
        {"ip": "192.0.2.2", "ipv6": "2001:db8::2", "subnet_id": "subnet-2"},
    ]
    if extra_address:
        requested.append({"ip": "192.0.2.3", "ipv6": "2001:db8::3", "subnet_id": "subnet-3"})

    converted = existing_endpoint(IpAddressCount=2, ResolverEndpointType="DUALSTACK")
    del converted["IpAddresses"], converted["Tags"]

    def with_ip_addresses(client, module, endpoint, changed=False):
        if endpoint["ResolverEndpointType"] != "DUALSTACK":
            return endpoint

        ip_addresses = [
            dict(ip_address, Ipv6=f"2001:db8::{index}")
            for index, ip_address in enumerate(existing_endpoint()["IpAddresses"], start=1)
        ]
        return dict(endpoint, IpAddresses=ip_addresses)

    client = Mock()
    client.update_resolver_endpoint.return_value = {"ResolverEndpoint": dict(converted, Status="UPDATING")}
    client.associate_resolver_endpoint_ip_address.return_value = {
        "ResolverEndpoint": in_flight_endpoint(IpAddressCount=3, ResolverEndpointType="DUALSTACK")
    }
    params = endpoint_params(ip_addresses=requested, resolver_endpoint_type="DUALSTACK")
    with (
        patch.object(plugin, "get_resolver_endpoint_by_name", return_value=existing_endpoint(IpAddressCount=2)),
        patch.object(plugin, "resolver_endpoint_with_ip_addresses", side_effect=with_ip_addresses),
        patch.object(plugin, "resolver_resource_with_tags", side_effect=lambda *args, **kwargs: args[2]),
        patch.object(plugin, "wait_for_resolver_endpoint_status", return_value=converted),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    endpoint = raised.value.values["resolver_endpoint"]
    assert (endpoint["status"], endpoint["ip_address_count"]) == (status, count)
    if check_mode:
        assert client.mock_calls == []
    else:
        client.update_resolver_endpoint.assert_called_once()
        assert client.associate_resolver_endpoint_ip_address.call_count == (1 if extra_address else 0)
        client.disassociate_resolver_endpoint_ip_address.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "tags", [{"Team": "R&D"}, {"Team": "a,b"}, {"Team#1": "x"}], ids=["ampersand", "comma", "hash-key"]
)
def test_tag_characters_aws_rejects_fail_before_aws(check_mode, tags):
    # Route 53 Resolver TagResource rejects these with InvalidParameterException (live), which an update reaches only
    # after its endpoint and address changes and the removal of purged tags.
    module = FakeModule(endpoint_params(state="present", tags=tags), check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": "tag keys and values must contain only letters, numbers, spaces, and _ . : / = + - @"
    }
    module.client.assert_not_called()


def test_tags_with_characters_aws_accepts_reach_aws():
    # Route 53 Resolver TagResource accepts these (live).
    module = FakeModule(endpoint_params(state="present", tags={"Team": "a b_.:/=+-@é1", "日本": "٣²"}))
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    module.client.assert_called_once()
