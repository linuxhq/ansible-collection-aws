import itertools
import random
from unittest.mock import ANY, Mock, patch

import pytest
from botocore.exceptions import WaiterError
from botocore.session import Session
from botocore.stub import Stubber

from ansible_collections.amazon.aws.plugins.module_utils.retries import RetryingBotoClientWrapper

from ansible_collections.linuxhq.aws.plugins.module_utils import wait as wait_utils
from ansible_collections.linuxhq.aws.plugins.modules import global_accelerator as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules import utils
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class FakeModule(utils.FakeModule):
    """Supply the wait bounds that the argument spec always sets, unless a test overrides them."""

    def __init__(self, params, **kwargs):
        super().__init__(dict({"wait_delay": 10, "wait_timeout": 600}, **params), **kwargs)


@pytest.mark.parametrize("check_mode", [False, True])
def test_listener_consolidation_releases_conflicting_ports_first(check_mode):
    def listener(arn, port):
        return {
            "listener_arn": arn,
            "protocol": "TCP",
            "client_affinity": "NONE",
            "port_ranges": [{"from_port": port, "to_port": port}],
        }

    current = [listener("arn:a", 80), listener("arn:b", 81), listener("arn:c", 90)]
    desired = {
        "protocol": "TCP",
        "client_affinity": "NONE",
        "endpoint_groups": None,
        "port_ranges": [{"from_port": 80, "to_port": 81}],
    }
    module = FakeModule({"listeners": [desired], "purge_listeners": True}, check_mode=check_mode)
    client = Mock()
    remaining = {item["listener_arn"]: item["port_ranges"] for item in current}
    operations = []

    def delete(c, m, accelerator_arn, arn, changed=False, deadline=None):
        remaining.pop(arn)
        operations.append(("delete", arn))

    def update(**request):
        for arn, ranges in remaining.items():
            if arn == request["ListenerArn"]:
                continue

            for old in ranges:
                for new in request["PortRanges"]:
                    assert new["ToPort"] < old["from_port"] or new["FromPort"] > old["to_port"]

        operations.append(("update", request["ListenerArn"]))
        return {
            "Listener": {
                "ClientAffinity": request["ClientAffinity"],
                "ListenerArn": request["ListenerArn"],
                "PortRanges": request["PortRanges"],
                "Protocol": request["Protocol"],
            }
        }

    client.update_listener.side_effect = update
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "delete_listener", side_effect=delete),
        patch.object(
            plugin, "wait_for_accelerator", side_effect=lambda *args, **kwargs: operations.append(("wait", None))
        ),
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    assert len(listeners) == 1
    assert listeners[0]["port_ranges"] == desired["port_ranges"]
    assert operations == (
        [] if check_mode else [("delete", "arn:b"), ("wait", None), ("update", "arn:a"), ("delete", "arn:c")]
    )


def test_absent_does_not_validate_unused_present_options():
    module = FakeModule(
        {
            "arn": None,
            "idempotency_token": "t" * 256,
            "ip_addresses": ["192.0.2.1"] * 3,
            "listeners": [{"port_ranges": []}],
            "name": "example",
            "state": "absent",
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "ensure_absent") as ensure_absent,
    ):
        plugin.main()

    ensure_absent.assert_called_once_with(None, module)


def test_absent_tolerates_accelerator_disappearing_during_delete():
    client = Mock()
    client.delete_accelerator.side_effect = plugin.ClientError(
        {"Error": {"Code": "AcceleratorNotFoundException", "Message": "gone"}},
        "DeleteAccelerator",
    )
    module = FakeModule({"wait": False})
    with (
        patch.object(
            plugin,
            "get_accelerator",
            return_value={"AcceleratorArn": "arn:accelerator", "Enabled": False},
        ),
        patch.object(plugin, "get_listeners", return_value=[]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    require.assert_called_once_with(
        module,
        client,
        "Global Accelerator",
        {"delete_accelerator": ("AcceleratorArn",)},
    )
    assert raised.value.values["changed"]


def test_absent_tolerates_accelerator_disappearing_while_waiting():
    client = Mock()
    module = FakeModule({"wait": False})
    with (
        patch.object(
            plugin,
            "get_accelerator",
            return_value={
                "AcceleratorArn": "arn:accelerator",
                "Enabled": True,
                "Status": "IN_PROGRESS",
            },
        ),
        patch.object(plugin, "wait_for_accelerator"),
        patch.object(plugin, "get_accelerator_by_arn", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values == {"changed": False, "state": "absent"}
    client.delete_accelerator.assert_not_called()


def test_absent_exits_when_the_waited_accelerator_is_deleted_elsewhere():
    raw_client = Session().create_client(
        "globalaccelerator",
        region_name="us-west-2",
        aws_access_key_id="EXAMPLE",
        aws_secret_access_key="EXAMPLE",
    )
    client = RetryingBotoClientWrapper(raw_client, plugin.AWSRetry.jittered_backoff(delay=0))
    module = FakeModule({"wait": True, "wait_delay": 1, "wait_timeout": 60})
    request = {"AcceleratorArn": "arn:accelerator"}
    with (
        Stubber(raw_client) as stubber,
        patch.object(
            plugin,
            "get_accelerator",
            return_value={"AcceleratorArn": "arn:accelerator", "Enabled": False, "Status": "IN_PROGRESS"},
        ),
        patch.object(plugin, "require_client_methods"),
        patch("botocore.waiter.time.sleep"),
        pytest.raises(ModuleExit) as raised,
    ):
        # Another run deletes the accelerator while this one waits for it to deploy.
        stubber.add_response("describe_accelerator", {"Accelerator": {"Status": "IN_PROGRESS"}}, request)
        for _call in range(2):
            stubber.add_client_error("describe_accelerator", "AcceleratorNotFoundException", expected_params=request)

        plugin.ensure_absent(client, module)

    stubber.assert_no_pending_responses()
    assert raised.value.values == {"changed": False, "state": "absent"}


@pytest.mark.parametrize(
    "params, message",
    [
        ({"arn": None, "name": None, "state": "present"}, "one of the following is required: arn, name"),
        ({"arn": None, "name": None, "state": "absent"}, "one of the following is required: arn, name"),
        (
            {"arn": "arn:accelerator", "name": None, "state": "present"},
            "state is present but all of the following are missing: name",
        ),
    ],
)
def test_null_identifiers_fail_before_any_aws_call(params, message):
    # Some ansible-core versions let an explicit null past required_if and required_one_of; the module checks the value.
    module = FakeModule(dict(params, idempotency_token=None, ip_addresses=None, listeners=None, tags=None))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client") as client_factory,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == message
    client_factory.assert_not_called()


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]


def test_describe_rejects_malformed_accelerator():
    client = Mock(describe_accelerator=Mock(return_value={"Accelerator": None}))
    module = FakeModule({})
    with (
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_accelerator_by_arn(client, module, "arn:accelerator")

    assert raised.value.values["msg"] == "Global Accelerator returned an invalid accelerator"


def test_listeners_reject_malformed_response_items():
    module = FakeModule({})
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_listeners(Mock(), module, "arn:accelerator")

    assert raised.value.values["msg"] == "Global Accelerator returned an invalid listener"


def test_listeners_keep_the_listed_port_range_order():
    # Live: ListListeners returns the ranges in the order they were sent and stored.
    listed = {
        "ClientAffinity": "NONE",
        "ListenerArn": "arn:listener",
        "PortRanges": [{"FromPort": 9000, "ToPort": 9001}, {"FromPort": 80, "ToPort": 81}],
        "Protocol": "TCP",
    }
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[listed]),
    ):
        listeners = plugin.get_listeners(Mock(), FakeModule({}), "arn:accelerator")

    assert listeners == [
        {
            "client_affinity": "NONE",
            "listener_arn": "arn:listener",
            "port_ranges": [{"from_port": 9000, "to_port": 9001}, {"from_port": 80, "to_port": 81}],
            "protocol": "TCP",
        }
    ]


def test_main_defers_sdk_validation_until_an_api_is_needed():
    endpoint_group = {
        "endpoint_configurations": None,
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    module = Mock(
        params={
            "arn": None,
            "idempotency_token": None,
            "ip_addresses": None,
            "listeners": [
                {
                    "endpoint_groups": [endpoint_group],
                    "port_ranges": [{"from_port": 443, "to_port": 443}],
                    "protocol": "TCP",
                }
            ],
            "name": "example",
            "purge_endpoint_groups": True,
            "purge_listeners": True,
            "purge_tags": True,
            "state": "present",
            "tags": {},
        },
        client=Mock(return_value=Mock()),
    )
    require_client_methods = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "ensure_present"),
        patch.object(plugin, "require_client_methods", require_client_methods),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "require_valid_tags"),
    ):
        plugin.main()

    require_client_methods.assert_not_called()


def test_sdk_validation_checks_endpoint_configuration_parameters():
    request = {
        "EndpointConfigurations": [
            {
                "AttachmentArn": "arn:attachment",
                "EndpointId": "endpoint-1",
                "Weight": 128,
            }
        ]
    }
    shape = Mock()
    shape.input_shape.members = {
        "EndpointConfigurations": Mock(member=Mock(members={"EndpointId": Mock(), "Weight": Mock()}))
    }
    client = Mock()
    client.meta.service_model.operation_model.return_value = shape
    module = Mock()
    plugin.require_endpoint_configuration_parameters(
        module,
        client,
        "create_endpoint_group",
        "CreateEndpointGroup",
        request,
    )

    assert any(
        "EndpointConfigurations parameter AttachmentArn" in call.kwargs["msg"]
        for call in module.fail_json.call_args_list
    )


def test_empty_ip_addresses_leave_assigned_addresses_unchanged():
    module = FakeModule(
        {
            "enabled": True,
            "ip_address_type": "IPV4",
            "ip_addresses": [],
            "listeners": None,
            "name": "example",
            "purge_tags": True,
            "tags": None,
            "wait": False,
        },
        check_mode=True,
    )
    current = {
        "AcceleratorArn": "arn:example",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "IpSets": [{"IpAddresses": ["203.0.113.1"]}],
        "Name": "example",
    }
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert not raised.value.values["changed"]
    assert raised.value.values["accelerator"]["ip_sets"] == [{"ip_addresses": ["203.0.113.1"]}]


def test_missing_explicit_arn_is_not_replaced_with_an_unselectable_resource():
    module = FakeModule(
        {
            "arn": "arn:missing",
            "enabled": True,
            "ip_address_type": "IPV4",
            "ip_addresses": None,
            "listeners": None,
            "name": "example",
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "get_accelerator", return_value=None),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert "does not exist" in raised.value.values["msg"]


def test_update_waits_for_deployment_and_rechecks_desired_state():
    client = Mock()
    module = FakeModule(
        {
            "enabled": True,
            "ip_address_type": "IPV4",
            "ip_addresses": None,
            "listeners": None,
            "name": "example",
            "purge_tags": True,
            "tags": None,
            "wait": False,
        }
    )
    transitioning = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": False,
        "IpAddressType": "IPV4",
        "Name": "example",
        "Status": "IN_PROGRESS",
    }
    deployed = dict(transitioning, Enabled=True, Status="DEPLOYED")
    with (
        patch.object(plugin, "get_accelerator", side_effect=[transitioning, deployed]),
        patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait_for_accelerator.assert_called_once_with(
        client, module, "arn:accelerator", "accelerator_deployed", deadline=ANY
    )
    assert not raised.value.values["changed"]
    client.update_accelerator.assert_not_called()


def test_port_ranges_are_normalized_before_comparison():
    assert plugin.normalized_port_ranges(
        [
            {"from_port": 443, "to_port": 443, "ignored": True},
            {"from_port": 80, "to_port": 81},
        ]
    ) == [
        {"from_port": 80, "to_port": 81},
        {"from_port": 443, "to_port": 443},
    ]


def test_endpoint_group_comparison_ignores_unmanaged_fields():
    current = {
        "endpoint_descriptions": [
            {
                "endpoint_id": "endpoint-1",
                "weight": 128,
                "client_ip_preservation_enabled": True,
            }
        ],
        "health_check_port": 443,
        "port_overrides": [{"listener_port": 80, "endpoint_port": 8080}],
    }
    desired = {
        "endpoint_configurations": [
            {
                "endpoint_id": "endpoint-1",
                "weight": 128,
                "client_ip_preservation_enabled": None,
            }
        ],
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": 443,
        "health_check_protocol": None,
        "port_overrides": [{"listener_port": 80, "endpoint_port": 8080}],
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }

    assert not plugin.endpoint_group_requires_update(current, desired)
    desired["health_check_port"] = 80
    assert plugin.endpoint_group_requires_update(current, desired)


def unset_endpoint_group(**settings):
    desired = {
        "endpoint_configurations": None,
        "endpoint_group_region": "us-west-2",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    desired.update(settings)
    return desired


@pytest.mark.parametrize(
    "current_protocol, desired_protocol, path, expected",
    [
        # AWS stores no path for TCP health checks, so a requested one never matches.
        ("TCP", None, "/health", False),
        ("TCP", "TCP", "/health", False),
        ("HTTP", None, "/health", True),
        ("HTTP", None, "/", False),
        ("TCP", "HTTP", "/", True),
    ],
)
def test_health_check_path_is_compared_only_for_http_health_checks(current_protocol, desired_protocol, path, expected):
    current = {"endpoint_group_region": "us-west-2", "health_check_protocol": current_protocol}
    if current_protocol != "TCP":
        current["health_check_path"] = "/"

    desired = unset_endpoint_group(health_check_path=path, health_check_protocol=desired_protocol)

    assert plugin.endpoint_group_requires_update(current, desired) is expected


# Values from a live CreateEndpointGroup in us-west-2 for each requested setting.
@pytest.mark.parametrize(
    "settings, default_health_check_port, expected",
    [
        (
            {},
            80,
            {
                "endpoint_descriptions": [],
                "health_check_interval_seconds": 30,
                "health_check_port": 80,
                "health_check_protocol": "TCP",
                "threshold_count": 3,
                "traffic_dial_percentage": 100.0,
            },
        ),
        (
            {"threshold_count": 5, "health_check_path": "/health"},
            8080,
            {
                "endpoint_descriptions": [],
                "health_check_interval_seconds": 30,
                "health_check_port": 8080,
                "health_check_protocol": "TCP",
                "threshold_count": 5,
                "traffic_dial_percentage": 100.0,
            },
        ),
        # Without a known default health check port, none is predicted.
        (
            {"health_check_protocol": "HTTP"},
            None,
            {
                "endpoint_descriptions": [],
                "health_check_interval_seconds": 30,
                "health_check_path": "/",
                "health_check_protocol": "HTTP",
                "threshold_count": 3,
                "traffic_dial_percentage": 100.0,
            },
        ),
    ],
)
def test_check_mode_endpoint_group_create_predicts_the_stored_settings(settings, default_health_check_port, expected):
    module = FakeModule({"purge_endpoint_groups": True}, check_mode=True)
    client = Mock()
    with patch.object(plugin, "get_endpoint_groups", return_value=[]):
        changed, groups = plugin.ensure_endpoint_groups(
            client,
            module,
            "arn:listener",
            [unset_endpoint_group(**settings)],
            default_health_check_port=default_health_check_port,
        )

    assert changed
    assert groups == [dict(expected, endpoint_group_region="us-west-2")]
    client.create_endpoint_group.assert_not_called()


def test_check_mode_listener_create_predicts_its_endpoint_group_health_check_port():
    listener = {
        "client_affinity": None,
        "endpoint_groups": [unset_endpoint_group()],
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    module = FakeModule(
        {"listeners": [listener], "purge_endpoint_groups": True, "purge_listeners": True}, check_mode=True
    )

    changed, listeners = plugin.ensure_listeners(Mock(), module, None)

    assert changed
    assert listeners[0]["endpoint_groups"][0]["health_check_port"] == 443


MULTIPLE_PORT_RANGES = [{"from_port": 9000, "to_port": 9001}, {"from_port": 7000, "to_port": 7001}]


# Live: AWS stores a listener's ranges in the order sent, lists them in that order, and checks health on the first
# port stored.
@pytest.mark.parametrize(
    "port_ranges, current_port_ranges, client_affinity, expected",
    [
        # A created or updated listener's ranges are sent sorted.
        (MULTIPLE_PORT_RANGES, None, None, 7000),
        (MULTIPLE_PORT_RANGES, [{"from_port": 5000, "to_port": 5000}], None, 7000),
        (MULTIPLE_PORT_RANGES, plugin.normalized_port_ranges(MULTIPLE_PORT_RANGES), "SOURCE_IP", 7000),
        (MULTIPLE_PORT_RANGES, MULTIPLE_PORT_RANGES, "SOURCE_IP", 7000),
        # An unchanged listener keeps the order in which AWS lists its ranges.
        (MULTIPLE_PORT_RANGES, plugin.normalized_port_ranges(MULTIPLE_PORT_RANGES), None, 7000),
        (MULTIPLE_PORT_RANGES, MULTIPLE_PORT_RANGES, None, 9000),
        (plugin.normalized_port_ranges(MULTIPLE_PORT_RANGES), MULTIPLE_PORT_RANGES, None, 9000),
        ([{"from_port": 443, "to_port": 443}], [{"from_port": 443, "to_port": 443}], None, 443),
    ],
)
def test_check_mode_endpoint_group_create_predicts_the_health_check_port_of_the_first_stored_listener_range(
    port_ranges, current_port_ranges, client_affinity, expected
):
    listener = {
        "client_affinity": client_affinity,
        "endpoint_groups": [unset_endpoint_group()],
        "port_ranges": port_ranges,
        "protocol": "TCP",
    }
    current_listeners = []
    if current_port_ranges is not None:
        current_listeners = [
            {
                "client_affinity": "NONE",
                "listener_arn": "arn:listener",
                "port_ranges": current_port_ranges,
                "protocol": "TCP",
            }
        ]

    module = FakeModule(
        {"listeners": [listener], "purge_endpoint_groups": True, "purge_listeners": True}, check_mode=True
    )
    client = Mock()
    with (
        patch.object(plugin, "get_listeners", return_value=current_listeners),
        patch.object(plugin, "get_endpoint_groups", return_value=[]),
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    assert listeners[0]["endpoint_groups"] == [
        {
            "endpoint_descriptions": [],
            "endpoint_group_region": "us-west-2",
            "health_check_interval_seconds": 30,
            "health_check_port": expected,
            "health_check_protocol": "TCP",
            "threshold_count": 3,
            "traffic_dial_percentage": 100.0,
        }
    ]
    # Listener ranges are returned sorted, whatever order AWS lists them in.
    assert listeners[0]["port_ranges"] == plugin.normalized_port_ranges(port_ranges)
    client.create_endpoint_group.assert_not_called()
    client.create_listener.assert_not_called()
    client.update_listener.assert_not_called()


def test_endpoint_group_attachment_does_not_require_update():
    current = {
        "endpoint_descriptions": [
            {
                "endpoint_id": "endpoint-1",
                "weight": 128,
            }
        ]
    }
    desired = {
        "endpoint_configurations": [
            {
                "attachment_arn": "arn:new",
                "client_ip_preservation_enabled": None,
                "endpoint_id": "endpoint-1",
                "weight": 128,
            }
        ],
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    assert not plugin.endpoint_group_requires_update(current, desired)
    # AWS endpoint descriptions never return the attachment ARN, so check mode does not predict it.
    assert plugin.predicted_endpoint_group(current, desired)["endpoint_descriptions"] == [
        {"endpoint_id": "endpoint-1", "weight": 128}
    ]


def test_listener_reconciliation_reuses_protocol_listener_for_update():
    current = [
        {
            "client_affinity": "NONE",
            "listener_arn": "arn:listener",
            "port_ranges": [{"from_port": 80, "to_port": 80}],
            "protocol": "TCP",
        }
    ]
    module = Mock(
        params={
            "listeners": [
                {
                    "client_affinity": "SOURCE_IP",
                    "endpoint_groups": None,
                    "port_ranges": [{"from_port": 443, "to_port": 443}],
                    "protocol": "TCP",
                }
            ],
            "purge_listeners": True,
        }
    )

    matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)

    assert matched == []
    assert updates[0][0] == current[0]
    assert updates[0][1]["port_ranges"] == [{"from_port": 443, "to_port": 443}]
    assert creates == []
    assert deletes == []


def test_listener_reconciliation_keeps_unlisted_listeners_without_purge():
    current = [review_listener("arn:listener", 443, 443)]
    module = FakeModule({"listeners": [review_desired(8080, 8080)], "purge_listeners": False})

    matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)

    assert matched == [(current[0], None)]
    assert updates == []
    assert creates == [review_desired(8080, 8080)]
    assert deletes == []


def listed_listeners(ports_by_arn):
    """Build TCP listeners in the listener ARN order get_listeners returns."""
    return [review_listener(arn, *ports_by_arn[arn]) for arn in sorted(ports_by_arn)]


def single_range(listener):
    port_range = listener["port_ranges"][0]
    return (port_range["from_port"], port_range["to_port"])


@pytest.mark.parametrize("reverse", [False, True], ids=["listed", "reversed"])
@pytest.mark.parametrize(
    ("ports_by_arn", "entries", "expected_updates", "expected_creates"),
    [
        # Listener ARNs end in random IDs, so both ARN orders occur; one of them used to cross the pairing.
        (
            {"arn:a": (80, 80), "arn:b": (443, 443)},
            [(80, 81), (443, 444)],
            {"arn:a": (80, 81), "arn:b": (443, 444)},
            [],
        ),
        (
            {"arn:a": (443, 443), "arn:b": (80, 80)},
            [(80, 81), (443, 444)],
            {"arn:a": (443, 444), "arn:b": (80, 81)},
            [],
        ),
        (
            {"arn:a": (80, 81), "arn:b": (90, 91)},
            [(89, 91), (80, 82)],
            {"arn:a": (80, 82), "arn:b": (89, 91)},
            [],
        ),
        # The most shared ports win over the lower ARN; the disjoint entry falls back to the listener left.
        (
            {"arn:a": (80, 81), "arn:b": (82, 85)},
            [(81, 84), (9000, 9000)],
            {"arn:a": (9000, 9000), "arn:b": (81, 84)},
            [],
        ),
        # An entry sharing as many ports with two listeners takes the lowest listener ARN.
        (
            {"arn:a": (82, 83), "arn:b": (80, 81)},
            [(81, 82), (9000, 9000)],
            {"arn:a": (81, 82), "arn:b": (9000, 9000)},
            [],
        ),
        # A listener goes to the entry sharing the most ports with it, and the other entry is created.
        (
            {"arn:a": (80, 89)},
            [(80, 81), (84, 89)],
            {"arn:a": (84, 89)},
            [(80, 81)],
        ),
        # A listener sharing as many ports with two entries goes to the entry with the lowest ports.
        (
            {"arn:a": (80, 83)},
            [(82, 83), (80, 81)],
            {"arn:a": (80, 81)},
            [(82, 83)],
        ),
        # As many entries as possible get a listener they overlap, even when one pair shares more ports: 1-10 updated
        # to 2-11 would leave 1 to 11-12, and each update would need ports the other listener still holds.
        (
            {"arn:a": (1, 10), "arn:b": (11, 12)},
            [(1, 1), (2, 11)],
            {"arn:a": (1, 1), "arn:b": (2, 11)},
            [],
        ),
        (
            {"arn:a": (11, 12), "arn:b": (1, 10)},
            [(1, 1), (2, 11)],
            {"arn:a": (2, 11), "arn:b": (1, 1)},
            [],
        ),
        (
            {"arn:a": (80, 84), "arn:b": (85, 86)},
            [(82, 85), (80, 81)],
            {"arn:a": (80, 81), "arn:b": (82, 85)},
            [],
        ),
    ],
)
def test_listener_reconciliation_pairs_entries_with_the_listeners_they_overlap(
    ports_by_arn, entries, expected_updates, expected_creates, reverse
):
    current = listed_listeners(ports_by_arn)
    entries = list(reversed(entries)) if reverse else entries
    module = FakeModule({"listeners": [review_desired(*ports) for ports in entries], "purge_listeners": True})

    matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)

    assert {current["listener_arn"]: single_range(desired) for current, desired in updates} == expected_updates
    assert [single_range(desired) for desired in creates] == expected_creates
    assert matched == []
    assert deletes == []


def disjoint_range_lists(last_port, size):
    """Yield every sorted list of 1 to size disjoint port ranges between port 1 and last_port."""
    ranges = [(start, end) for start in range(1, last_port + 1) for end in range(start, last_port + 1)]
    for count in range(1, size + 1):
        for chosen in itertools.combinations(ranges, count):
            if all(left[1] < right[0] for left, right in itertools.pairwise(chosen)):
                yield list(chosen)


@pytest.mark.parametrize("reverse_entries", [False, True], ids=["listed", "reversed"])
@pytest.mark.parametrize("reverse_arns", [False, True], ids=["arns-ascending", "arns-descending"])
def test_single_range_listener_moves_never_have_circular_dependencies(reverse_arns, reverse_entries):
    module = FakeModule({"listeners": [], "purge_listeners": True})
    circular = []
    for listener_ranges in disjoint_range_lists(5, 3):
        arns = [f"arn:{index}" for index in range(len(listener_ranges))]
        current = listed_listeners(dict(zip(reversed(arns) if reverse_arns else arns, listener_ranges)))
        for entry_ranges in disjoint_range_lists(5, 3):
            entries = list(reversed(entry_ranges)) if reverse_entries else entry_ranges
            module.params["listeners"] = [review_desired(*ports) for ports in entries]
            updates = plugin.reconcile_listeners(module, current)[1]
            try:
                plugin.ordered_listener_updates(module, updates)
            except ModuleFail:
                circular.append((listener_ranges, entries))

    assert circular == []


def multi_range_desired(*ranges):
    return dict(review_desired(*ranges[0]), port_ranges=[{"from_port": start, "to_port": end} for start, end in ranges])


@pytest.mark.parametrize("arns", list(itertools.permutations(["arn:a", "arn:b", "arn:c"])))
def test_listener_reconciliation_skips_pairs_that_leave_circular_dependencies(arns):
    # 1-10 and 11-20 share the most ports with X and Y, but each of those updates needs a port the other listener still
    # holds; updating 30 to Y instead lets 11-20 be deleted first.
    low_arn, single_arn, high_arn = arns
    current = listed_listeners({low_arn: (1, 10), single_arn: (30, 30), high_arn: (11, 20)})
    x = multi_range_desired((1, 9), (11, 11))
    y = multi_range_desired((10, 10), (12, 20), (30, 30))
    module = FakeModule({"listeners": [x, y], "purge_listeners": True})

    matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)

    assert {current["listener_arn"]: desired["port_ranges"] for current, desired in updates} == {
        low_arn: x["port_ranges"],
        single_arn: y["port_ranges"],
    }
    assert [current["listener_arn"] for current in deletes] == [high_arn]
    assert matched == []
    assert creates == []
    assert plugin.listener_update_order(updates) is not None


def random_port_ranges(generator, ports, count):
    """Split up to count disjoint port ranges, taken from ports, into groups of one to three ranges."""
    starts = sorted(generator.sample(ports, min(len(ports), 2 * count)))
    ranges = [(starts[index], starts[index + 1]) for index in range(0, len(starts) - 1, 2)]
    generator.shuffle(ranges)
    groups = []
    while ranges:
        size = generator.randint(1, min(3, len(ranges)))
        groups.append(sorted(ranges[:size]))
        ranges = ranges[size:]

    return groups


def test_listener_reconciliation_never_fails_where_the_protocol_pairing_alone_succeeds():
    generator = random.Random(0)
    regressions = []
    for unused_case in range(3000):
        listener_groups = random_port_ranges(generator, range(1, 13), generator.randint(1, 6))
        entry_groups = random_port_ranges(generator, range(1, 13), generator.randint(1, 6))
        arns = generator.sample(range(10), len(listener_groups))
        current = sorted(
            (
                dict(review_listener(f"arn:{arn}", 0, 0), port_ranges=multi_range_desired(*ranges)["port_ranges"])
                for arn, ranges in zip(arns, listener_groups)
            ),
            key=lambda item: item["listener_arn"],
        )
        entries = [multi_range_desired(*ranges) for ranges in entry_groups]
        module = FakeModule({"listeners": entries, "purge_listeners": True})

        # The rule before overlap pairing: exact matches, then entries in order take the first remaining listener.
        exact = {plugin.listener_identity(item) for item in current} & {
            plugin.listener_identity(item) for item in entries
        }
        protocol_pairs = plugin.protocol_listener_pairs(
            [item for item in current if plugin.listener_identity(item) not in exact],
            [item for item in entries if plugin.listener_identity(item) not in exact],
        )[0]
        updates = plugin.reconcile_listeners(module, current)[1]
        if plugin.listener_update_order(protocol_pairs) is not None and plugin.listener_update_order(updates) is None:
            regressions.append((listener_groups, arns, entry_groups))

    assert regressions == []


def test_listener_reconciliation_without_purge_never_reuses_an_overlapping_listener():
    current = [review_listener("arn:listener", 80, 80)]
    module = FakeModule({"listeners": [review_desired(80, 81)], "purge_listeners": False})

    matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)

    assert matched == [(current[0], None)]
    assert updates == []
    assert creates == [review_desired(80, 81)]
    assert deletes == []


def updated_listener_response(**request):
    return {
        "Listener": {
            "ClientAffinity": request["ClientAffinity"],
            "ListenerArn": request["ListenerArn"],
            "PortRanges": request["PortRanges"],
            "Protocol": request["Protocol"],
        }
    }


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("arns", [("arn:a", "arn:b"), ("arn:b", "arn:a")], ids=["http-first", "https-first"])
def test_overlapping_listener_moves_update_their_own_listeners(check_mode, arns):
    http_arn, https_arn = arns
    current = listed_listeners({http_arn: (80, 80), https_arn: (443, 443)})
    module = FakeModule(
        {
            "listeners": [review_desired(80, 81), review_desired(443, 444)],
            "purge_endpoint_groups": True,
            "purge_listeners": True,
        },
        check_mode=check_mode,
    )
    client = Mock()
    active = {item["listener_arn"]: item for item in current}

    def update(**request):
        # AWS rejects ports that another listener of the protocol still holds.
        target = review_listener(
            request["ListenerArn"], request["PortRanges"][0]["FromPort"], request["PortRanges"][0]["ToPort"]
        )
        assert not any(
            plugin.listeners_overlap(target, other) for arn, other in active.items() if arn != target["listener_arn"]
        )
        active[target["listener_arn"]] = target
        return updated_listener_response(**request)

    client.update_listener.side_effect = update
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(plugin, "wait_for_accelerator"),
        patch.object(plugin, "delete_listener") as delete,
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    # Check mode returns what the real run returns.
    assert changed
    assert listeners == [review_listener(http_arn, 80, 81), review_listener(https_arn, 443, 444)]
    assert client.update_listener.call_count == (0 if check_mode else 2)
    client.create_listener.assert_not_called()
    delete.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("arns", [("arn:a", "arn:b"), ("arn:b", "arn:a")], ids=["http-first", "https-first"])
@pytest.mark.parametrize("other_ports", [(80, 81), (8080, 8080)], ids=["overlapping", "disjoint"])
def test_unmanaged_endpoint_groups_stay_on_the_listener_whose_ports_overlap(check_mode, arns, other_ports):
    http_arn, https_arn = arns
    current = listed_listeners({http_arn: (80, 80), https_arn: (443, 443)})
    # The 443-444 entry leaves its endpoint groups unmanaged; the other entry removes every group of its listener.
    entries = [review_desired(443, 444), dict(review_desired(*other_ports), endpoint_groups=[])]
    endpoint_groups = {
        http_arn: [],
        https_arn: [{"endpoint_group_arn": "arn:group", "endpoint_group_region": "us-east-1"}],
    }
    module = FakeModule(
        {"listeners": entries, "purge_endpoint_groups": True, "purge_listeners": True},
        check_mode=check_mode,
    )
    client = Mock()
    client.update_listener.side_effect = updated_listener_response
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(
            plugin,
            "get_endpoint_groups",
            side_effect=lambda client, module, listener_arn, changed=False: endpoint_groups[listener_arn],
        ) as get_endpoint_groups,
        patch.object(plugin, "delete_endpoint_group") as delete_endpoint_group,
        patch.object(plugin, "wait_for_accelerator"),
        patch.object(plugin, "delete_listener") as delete_listener,
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    delete_endpoint_group.assert_not_called()
    delete_listener.assert_not_called()
    assert changed
    assert {single_range(listener): listener["listener_arn"] for listener in listeners} == {
        (443, 444): https_arn,
        other_ports: http_arn,
    }
    assert [listener.get("endpoint_groups") for listener in listeners] == (
        [[], None] if other_ports < (443, 444) else [None, []]
    )
    assert [call.args[2] for call in get_endpoint_groups.call_args_list] == [http_arn]
    if check_mode:
        client.update_listener.assert_not_called()
    else:
        assert sorted(
            (call.kwargs["ListenerArn"], call.kwargs["PortRanges"]) for call in client.update_listener.call_args_list
        ) == sorted(
            [
                (https_arn, [{"FromPort": 443, "ToPort": 444}]),
                (http_arn, [{"FromPort": other_ports[0], "ToPort": other_ports[1]}]),
            ]
        )


@pytest.mark.parametrize("check_mode", [False, True])
def test_listener_creation_without_purge_leaves_unlisted_listeners_unchanged(check_mode):
    current = review_listener("arn:listener", 443, 443)
    module = FakeModule(
        {"listeners": [review_desired(8080, 8080)], "purge_listeners": False},
        check_mode=check_mode,
    )
    client = Mock()
    client.create_listener.return_value = {
        "Listener": {
            "ClientAffinity": "NONE",
            "ListenerArn": "arn:new",
            "PortRanges": [{"FromPort": 8080, "ToPort": 8080}],
            "Protocol": "TCP",
        }
    }
    with (
        patch.object(plugin, "get_listeners", return_value=[current]),
        patch.object(plugin, "wait_for_accelerator"),
        patch.object(plugin, "delete_listener") as delete,
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    client.update_listener.assert_not_called()
    delete.assert_not_called()
    if check_mode:
        client.create_listener.assert_not_called()
    else:
        client.create_listener.assert_called_once()
        assert client.create_listener.call_args.kwargs["PortRanges"] == [{"FromPort": 8080, "ToPort": 8080}]

    created = {"client_affinity": "NONE", "port_ranges": [{"from_port": 8080, "to_port": 8080}], "protocol": "TCP"}
    if not check_mode:
        created["listener_arn"] = "arn:new"

    assert listeners == [current, created]


@pytest.mark.parametrize("check_mode", [False, True])
def test_unchanged_listeners_listed_unsorted_match_and_return_sorted_ranges(check_mode):
    listed_ranges = [{"from_port": 9000, "to_port": 9001}, {"from_port": 80, "to_port": 81}]
    current = [
        {"client_affinity": "NONE", "listener_arn": "arn:tcp", "port_ranges": listed_ranges, "protocol": "TCP"},
        {"client_affinity": "NONE", "listener_arn": "arn:udp", "port_ranges": listed_ranges, "protocol": "UDP"},
    ]
    desired = {
        "client_affinity": None,
        "endpoint_groups": None,
        "port_ranges": listed_ranges,
        "protocol": "TCP",
    }
    module = FakeModule(
        {"listeners": [desired], "purge_endpoint_groups": True, "purge_listeners": False},
        check_mode=check_mode,
    )
    client = Mock()
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(plugin, "wait_for_accelerator") as waiter,
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    sorted_ranges = [{"from_port": 80, "to_port": 81}, {"from_port": 9000, "to_port": 9001}]
    assert not changed
    assert listeners == [dict(listener, port_ranges=sorted_ranges) for listener in current]
    client.create_listener.assert_not_called()
    client.update_listener.assert_not_called()
    client.delete_listener.assert_not_called()
    waiter.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_listener_creation_without_purge_fails_on_unlisted_overlap(check_mode):
    current = review_listener("arn:listener", 443, 443)
    module = FakeModule(
        {"listeners": [review_desired(440, 450)], "purge_listeners": False},
        check_mode=check_mode,
    )
    client = Mock()
    with (
        patch.object(plugin, "get_listeners", return_value=[current]),
        patch.object(plugin, "delete_listener") as delete,
        pytest.raises(ModuleFail, match="overlap retained listener arn:listener") as raised,
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator")

    assert raised.value.values["changed"] is False
    delete.assert_not_called()
    client.update_listener.assert_not_called()
    client.create_listener.assert_not_called()


def test_provider_limits_are_rejected():
    cases = [
        (
            {"name": "n" * 256, "ip_addresses": None, "listeners": None},
            "name must contain at most 255 characters",
        ),
        (
            {
                "idempotency_token": "t" * 256,
                "ip_addresses": None,
                "listeners": None,
            },
            "idempotency_token must contain at most 255 characters",
        ),
        (
            {"ip_addresses": ["192.0.2.1"] * 3, "listeners": None},
            "ip_addresses must contain at most 2 entries",
        ),
        (
            {"ip_addresses": ["a" * 46], "listeners": None},
            "ip_addresses entries must contain at most 45 characters",
        ),
        (
            {"ip_addresses": ["not-an-ip"], "listeners": None},
            "ip_addresses entries must be valid IPv4 addresses: not-an-ip",
        ),
        (
            {"ip_addresses": ["192.0.2.1"] * 2, "listeners": None},
            "ip_addresses entries must be unique",
        ),
        (
            {
                "ip_addresses": None,
                "listeners": [
                    {
                        "port_ranges": [{"from_port": 1, "to_port": 1}] * 11,
                    }
                ],
            },
            "listeners entries allow at most 10 port_ranges entries",
        ),
        (
            {
                "ip_addresses": None,
                "listeners": [{"port_ranges": []}],
            },
            "listeners entries require at least one port_ranges entry",
        ),
        (
            {
                "ip_addresses": None,
                "listeners": [
                    {
                        "endpoint_groups": [{"endpoint_group_region": f"region-{index}"}],
                        "port_ranges": [{"from_port": index + 1, "to_port": index + 1}],
                    }
                    for index in range(43)
                ],
            },
            "listeners must contain at most 42 endpoint groups in total",
        ),
        (
            {
                "ip_addresses": None,
                "listeners": [{"port_ranges": [{"from_port": 0, "to_port": 443}]}],
            },
            "port_ranges entries must be between 1 and 65535",
        ),
        (
            {
                "ip_addresses": None,
                "listeners": [{"port_ranges": [{"from_port": 443, "to_port": 80}]}],
            },
            "port_ranges entries require from_port to be less than or equal to to_port",
        ),
        (
            {
                "ip_addresses": None,
                "listeners": [
                    {
                        "port_ranges": [
                            {"from_port": 80, "to_port": 90},
                            {"from_port": 90, "to_port": 100},
                        ]
                    }
                ],
            },
            "listeners port_ranges entries must not overlap",
        ),
    ]
    for params, message in cases:
        assert_module_rejects(plugin, dict(params, state="present"), message)


def test_listener_port_ranges_must_not_overlap_across_listeners():
    assert_module_rejects(
        plugin,
        {
            "ip_addresses": None,
            "listeners": [
                {
                    "port_ranges": [{"from_port": 80, "to_port": 90}],
                    "protocol": "TCP",
                },
                {
                    "port_ranges": [{"from_port": 90, "to_port": 100}],
                    "protocol": "TCP",
                },
            ],
            "state": "present",
        },
        "listeners port_ranges entries must not overlap",
    )


def present_params(listeners):
    return {
        "arn": None,
        "enabled": None,
        "idempotency_token": None,
        "ip_address_type": None,
        "ip_addresses": None,
        "listeners": listeners,
        "name": "example",
        "purge_endpoint_groups": True,
        "purge_listeners": True,
        "purge_tags": True,
        "state": "present",
        "tags": None,
        "wait": True,
    }


def test_listeners_with_different_protocols_may_share_ports():
    # Live: AWS accepts a UDP 53 listener next to a TCP 53 listener on the same accelerator.
    listeners = [
        {
            "client_affinity": None,
            "endpoint_groups": None,
            "port_ranges": [{"from_port": 53, "to_port": 53}],
            "protocol": protocol,
        }
        for protocol in ("TCP", "UDP")
    ]
    module = FakeModule(present_params(listeners))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


def port_override_listeners(listener_port):
    endpoint_group = {
        "endpoint_configurations": None,
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": [{"endpoint_port": 8080, "listener_port": listener_port}],
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    return [
        {
            "client_affinity": None,
            "endpoint_groups": [endpoint_group],
            "port_ranges": [{"from_port": 443, "to_port": 443}, {"from_port": 80, "to_port": 81}],
            "protocol": "TCP",
        }
    ]


@pytest.mark.parametrize("listener_port", [79, 82, 442, 444])
def test_port_override_outside_the_listener_port_ranges_fails_before_any_aws_call(listener_port):
    # Live: Create/UpdateEndpointGroup reject such an override with InvalidArgumentException, which a real run reaches
    # only after creating or updating the accelerator and its listeners.
    module = FakeModule(present_params(port_override_listeners(listener_port)))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client") as client_factory,
        patch.object(plugin, "ensure_present") as ensure_present,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == (
        f"Endpoint group us-east-1 port_overrides listener_port {listener_port} "
        "must be within the listener's port_ranges"
    )
    client_factory.assert_not_called()
    ensure_present.assert_not_called()


@pytest.mark.parametrize("listener_port", [80, 81, 443])
def test_port_override_within_any_listener_port_range_is_accepted(listener_port):
    module = FakeModule(present_params(port_override_listeners(listener_port)))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


EIP_ALLOCATION_ID = "eipalloc-0123456789abcdef0"
EIP_ARN = f"arn:aws:ec2:us-west-2:123456789012:elastic-ip/{EIP_ALLOCATION_ID}"


def client_ip_preservation_listeners(endpoint_id, client_ip_preservation_enabled):
    endpoint_group = {
        "endpoint_configurations": [
            {
                "attachment_arn": None,
                "client_ip_preservation_enabled": client_ip_preservation_enabled,
                "endpoint_id": endpoint_id,
                "weight": 128,
            }
        ],
        "endpoint_group_region": "us-west-2",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    return [
        {
            "client_affinity": None,
            "endpoint_groups": [endpoint_group],
            "port_ranges": [{"from_port": 443, "to_port": 443}],
            "protocol": "TCP",
        }
    ]


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("endpoint_id", [EIP_ALLOCATION_ID, EIP_ARN], ids=["allocation-id", "arn"])
def test_client_ip_preservation_on_an_elastic_ip_endpoint_fails_before_any_aws_call(check_mode, endpoint_id):
    # Live: Create/UpdateEndpointGroup reject it for an Elastic IP address given by allocation ID or by ARN with
    # InvalidArgumentException, which a real run reaches only after creating or updating the accelerator and listeners.
    module = FakeModule(
        present_params(client_ip_preservation_listeners(endpoint_id, True)),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client") as client_factory,
        patch.object(plugin, "ensure_present") as ensure_present,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": (
            f"Endpoint group us-west-2 endpoint {endpoint_id} is an Elastic IP address, "
            "which does not support client_ip_preservation_enabled=true"
        )
    }
    client_factory.assert_not_called()
    ensure_present.assert_not_called()


@pytest.mark.parametrize(
    ("endpoint_id", "client_ip_preservation_enabled"),
    [
        (EIP_ALLOCATION_ID, False),
        (EIP_ALLOCATION_ID, None),
        (EIP_ARN, False),
        ("i-0123456789abcdef0", True),
        ("arn:aws:ec2:us-west-2:123456789012:instance/i-0123456789abcdef0", True),
        ("arn:aws:elasticloadbalancing:us-west-2:123456789012:loadbalancer/app/example/0123456789abcdef", True),
    ],
    ids=["eip-false", "eip-omitted", "eip-arn-false", "instance", "instance-arn", "load-balancer"],
)
def test_client_ip_preservation_is_left_to_aws_for_other_endpoints(endpoint_id, client_ip_preservation_enabled):
    module = FakeModule(present_params(client_ip_preservation_listeners(endpoint_id, client_ip_preservation_enabled)))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


ACCELERATOR_ARN = "arn:aws:globalaccelerator::123456789012:accelerator/01234567-89ab-cdef-0123-456789abcdef"
OTHER_ALLOCATION_ID = "eipalloc-0fedcba9876543210"
OTHER_ACCOUNT_EIP_ARN = f"arn:aws:ec2:us-west-2:111122223333:elastic-ip/{EIP_ALLOCATION_ID}"
INSTANCE_ID = "i-0123456789abcdef0"
INSTANCE_ARN = f"arn:aws:ec2:us-west-2:123456789012:instance/{INSTANCE_ID}"
LOAD_BALANCER_ARN = "arn:aws:elasticloadbalancing:us-west-2:123456789012:loadbalancer/app/example/0123456789abcdef"
# The partition and account of ACCELERATOR_ARN, and the region of the endpoint groups below.
SCOPE = ("aws", "123456789012", "us-west-2")


def endpoint_group_response(*endpoint_ids, weight=128):
    """An endpoint group as AWS returned it live for Elastic IP address endpoints, whichever form created them."""
    return {
        "EndpointDescriptions": [
            {
                "ClientIPPreservationEnabled": False,
                "EndpointId": endpoint_id,
                "HealthState": "UNHEALTHY",
                "Weight": weight,
            }
            for endpoint_id in endpoint_ids
        ],
        "EndpointGroupArn": "arn:group",
        "EndpointGroupRegion": "us-west-2",
        "HealthCheckIntervalSeconds": 30,
        "HealthCheckPort": 443,
        "HealthCheckProtocol": "TCP",
        "ThresholdCount": 3,
        "TrafficDialPercentage": 100.0,
    }


def listed_endpoint_group(*endpoint_ids, weight=128):
    return plugin.boto3_resource_to_ansible_dict(
        endpoint_group_response(*endpoint_ids, weight=weight), transform_tags=False, force_tags=False
    )


def endpoint_group_with(*endpoint_ids, weight=128):
    return unset_endpoint_group(
        endpoint_configurations=[
            {
                "attachment_arn": None,
                "client_ip_preservation_enabled": None,
                "endpoint_id": endpoint_id,
                "weight": weight,
            }
            for endpoint_id in endpoint_ids
        ]
    )


# Live: AWS accepts a same-account Elastic IP address or EC2 instance given by ARN, but stores and lists it by
# allocation ID or instance ID.
@pytest.mark.parametrize(
    "listed_ids, endpoint_ids, weight, expected",
    [
        ([EIP_ALLOCATION_ID], [EIP_ARN], 128, False),
        ([EIP_ALLOCATION_ID], [EIP_ALLOCATION_ID], 128, False),
        ([EIP_ARN], [EIP_ARN], 128, False),
        ([EIP_ALLOCATION_ID], [EIP_ARN], 200, True),
        ([EIP_ALLOCATION_ID], [f"arn:aws:ec2:us-west-2:123456789012:elastic-ip/{OTHER_ALLOCATION_ID}"], 128, True),
        ([EIP_ALLOCATION_ID, OTHER_ALLOCATION_ID], [EIP_ARN], 128, True),
        ([EIP_ALLOCATION_ID], [EIP_ARN, OTHER_ALLOCATION_ID], 128, True),
        ([EIP_ALLOCATION_ID, OTHER_ALLOCATION_ID], [EIP_ARN, OTHER_ALLOCATION_ID], 128, False),
        ([INSTANCE_ID], [INSTANCE_ARN], 128, False),
        ([INSTANCE_ID], [INSTANCE_ARN], 200, True),
        ([LOAD_BALANCER_ARN], [LOAD_BALANCER_ARN], 128, False),
        ([INSTANCE_ID], [f"arn:aws:ec2:us-west-2:123456789012:volume/{INSTANCE_ID}"], 128, True),
    ],
    ids=[
        "listed-id",
        "same-id",
        "listed-arn",
        "weight",
        "other-allocation-arn",
        "extra-listed",
        "missing-listed",
        "mixed-forms",
        "instance",
        "instance-weight",
        "load-balancer",
        "other-ec2-resource-type",
    ],
)
def test_an_ec2_arn_matches_its_listed_resource_id(listed_ids, endpoint_ids, weight, expected):
    current = listed_endpoint_group(*listed_ids)
    desired = endpoint_group_with(*endpoint_ids, weight=weight)

    assert plugin.endpoint_group_requires_update(current, desired, SCOPE) is expected


# What AWS lists for an EC2 ARN outside the accelerator's partition and account or the group's region is unknown, so it
# matches only as given.
@pytest.mark.parametrize(
    "endpoint_id, scope",
    [
        (OTHER_ACCOUNT_EIP_ARN, SCOPE),
        (f"arn:aws:ec2:us-east-1:123456789012:elastic-ip/{EIP_ALLOCATION_ID}", SCOPE),
        (f"arn:aws-cn:ec2:us-west-2:123456789012:elastic-ip/{EIP_ALLOCATION_ID}", SCOPE),
        (f"arn:aws:ec2:us-west-2:111122223333:instance/{INSTANCE_ID}", SCOPE),
        (EIP_ARN, None),
    ],
    ids=["other-account", "other-region", "other-partition", "other-account-instance", "no-accelerator"],
)
def test_an_ec2_arn_outside_the_accelerator_scope_matches_only_as_given(endpoint_id, scope):
    resource_id = endpoint_id.rsplit("/", 1)[1]

    assert plugin.endpoint_group_requires_update(
        listed_endpoint_group(resource_id), endpoint_group_with(endpoint_id), scope
    )
    assert not plugin.endpoint_group_requires_update(
        listed_endpoint_group(endpoint_id), endpoint_group_with(endpoint_id), scope
    )


def test_the_scope_is_the_accelerator_partition_and_account_and_the_group_region():
    assert plugin.endpoint_group_scope(ACCELERATOR_ARN, "us-west-2") == SCOPE
    assert plugin.endpoint_group_scope(None, "us-west-2") is None


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "listed_id, endpoint_id", [(EIP_ALLOCATION_ID, EIP_ARN), (INSTANCE_ID, INSTANCE_ARN)], ids=["eip", "instance"]
)
def test_an_ec2_endpoint_group_requested_by_arn_converges(check_mode, listed_id, endpoint_id):
    current = listed_endpoint_group(listed_id)
    client = Mock()
    module = FakeModule({"purge_endpoint_groups": True}, check_mode=check_mode)
    with patch.object(plugin, "get_endpoint_groups", return_value=[current]):
        changed, groups = plugin.ensure_endpoint_groups(
            client, module, "arn:listener", [endpoint_group_with(endpoint_id)], accelerator_arn=ACCELERATOR_ARN
        )

    assert changed is False
    assert groups == [current]
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [False, True])
def test_listener_reconciliation_passes_the_accelerator_to_endpoint_group_matching(check_mode):
    listener = {
        "client_affinity": None,
        "endpoint_groups": [endpoint_group_with(EIP_ARN)],
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    current_listener = {
        "client_affinity": "NONE",
        "listener_arn": "arn:listener",
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    current = listed_endpoint_group(EIP_ALLOCATION_ID)
    module = FakeModule(
        {"listeners": [listener], "purge_endpoint_groups": True, "purge_listeners": True}, check_mode=check_mode
    )
    client = Mock()
    with (
        patch.object(plugin, "get_listeners", return_value=[current_listener]),
        patch.object(plugin, "get_endpoint_groups", return_value=[current]),
    ):
        changed, listeners = plugin.ensure_listeners(client, module, ACCELERATOR_ARN)

    assert changed is False
    assert listeners[0]["endpoint_groups"] == [current]
    assert client.mock_calls == []


def run_endpoint_group_change(check_mode, current, desired, response):
    client = Mock()
    client.create_endpoint_group.return_value = {"EndpointGroup": response}
    client.update_endpoint_group.return_value = {"EndpointGroup": response}
    module = FakeModule({"purge_endpoint_groups": True}, check_mode=check_mode)
    with patch.object(plugin, "get_endpoint_groups", return_value=[current] if current else []):
        changed, groups = plugin.ensure_endpoint_groups(
            client, module, "arn:listener", [desired], accelerator_arn=ACCELERATOR_ARN
        )

    assert changed
    return client, groups[0]


def test_an_update_sends_the_requested_arn_and_check_mode_predicts_the_listed_id():
    current = listed_endpoint_group(EIP_ALLOCATION_ID)
    desired = endpoint_group_with(EIP_ARN, weight=200)
    # Live: UpdateEndpointGroup given the ARN returns the endpoint under its allocation ID.
    response = endpoint_group_response(EIP_ALLOCATION_ID, weight=200)

    client, real = run_endpoint_group_change(False, current, desired, response)
    check_client, predicted = run_endpoint_group_change(True, current, desired, response)

    client.update_endpoint_group.assert_called_once_with(
        EndpointConfigurations=[{"EndpointId": EIP_ARN, "Weight": 200}],
        EndpointGroupArn="arn:group",
        aws_retry=True,
    )
    assert real == listed_endpoint_group(EIP_ALLOCATION_ID, weight=200)
    assert check_client.mock_calls == []
    # Check mode does not predict the health state or the client IP preservation default (carry-over).
    assert predicted["endpoint_descriptions"] == [{"endpoint_id": EIP_ALLOCATION_ID, "weight": 200}]
    assert dict(predicted, endpoint_descriptions=None) == dict(real, endpoint_descriptions=None)


def test_a_create_sends_the_requested_arn_and_check_mode_predicts_the_listed_id():
    desired = unset_endpoint_group(
        endpoint_configurations=endpoint_group_with(EIP_ARN)["endpoint_configurations"], health_check_port=443
    )
    # Live: CreateEndpointGroup given the ARN returns the endpoint under its allocation ID.
    response = endpoint_group_response(EIP_ALLOCATION_ID)

    client, real = run_endpoint_group_change(False, None, desired, response)
    check_client, predicted = run_endpoint_group_change(True, None, desired, response)

    assert client.create_endpoint_group.call_args.kwargs["EndpointConfigurations"] == [
        {"EndpointId": EIP_ARN, "Weight": 128}
    ]
    assert real == listed_endpoint_group(EIP_ALLOCATION_ID)
    assert check_client.mock_calls == []
    assert predicted["endpoint_descriptions"] == [{"endpoint_id": EIP_ALLOCATION_ID, "weight": 128}]
    # AWS assigns the group ARN on create.
    unpredicted = ("endpoint_descriptions", "endpoint_group_arn")
    assert {key: value for key, value in predicted.items() if key not in unpredicted} == {
        key: value for key, value in real.items() if key not in unpredicted
    }


@pytest.mark.parametrize(
    "accelerator_arn, listener_arn, endpoint_id, expected",
    [
        (ACCELERATOR_ARN, "arn:listener", EIP_ARN, EIP_ALLOCATION_ID),
        (ACCELERATOR_ARN, None, EIP_ARN, EIP_ALLOCATION_ID),
        # A new accelerator has no ARN yet, so its account is unknown.
        (None, None, EIP_ARN, EIP_ARN),
        # What AWS lists for another account's or region's address is unknown.
        (ACCELERATOR_ARN, "arn:listener", OTHER_ACCOUNT_EIP_ARN, OTHER_ACCOUNT_EIP_ARN),
        (
            ACCELERATOR_ARN,
            "arn:listener",
            f"arn:aws:ec2:us-east-1:123456789012:elastic-ip/{EIP_ALLOCATION_ID}",
            f"arn:aws:ec2:us-east-1:123456789012:elastic-ip/{EIP_ALLOCATION_ID}",
        ),
        (ACCELERATOR_ARN, "arn:listener", EIP_ALLOCATION_ID, EIP_ALLOCATION_ID),
        (ACCELERATOR_ARN, "arn:listener", INSTANCE_ARN, INSTANCE_ID),
        (ACCELERATOR_ARN, "arn:listener", LOAD_BALANCER_ARN, LOAD_BALANCER_ARN),
    ],
    ids=[
        "existing-listener",
        "new-listener",
        "new-accelerator",
        "other-account",
        "other-region",
        "allocation-id",
        "instance",
        "load-balancer",
    ],
)
def test_check_mode_create_predicts_the_listed_id_of_an_ec2_arn(accelerator_arn, listener_arn, endpoint_id, expected):
    listener = {
        "client_affinity": None,
        "endpoint_groups": [endpoint_group_with(endpoint_id)],
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    current_listeners = []
    if listener_arn is not None:
        current_listeners = [
            {
                "client_affinity": "NONE",
                "listener_arn": listener_arn,
                "port_ranges": [{"from_port": 443, "to_port": 443}],
                "protocol": "TCP",
            }
        ]

    module = FakeModule(
        {"listeners": [listener], "purge_endpoint_groups": True, "purge_listeners": True}, check_mode=True
    )
    client = Mock()
    with (
        patch.object(plugin, "get_listeners", return_value=current_listeners),
        patch.object(plugin, "get_endpoint_groups", return_value=[]),
    ):
        changed, listeners = plugin.ensure_listeners(client, module, accelerator_arn)

    assert changed
    assert listeners[0]["endpoint_groups"][0]["endpoint_descriptions"] == [{"endpoint_id": expected, "weight": 128}]
    assert client.mock_calls == []


def test_endpoint_groups_reject_duplicate_regions_and_endpoints():
    endpoint = {
        "attachment_arn": None,
        "client_ip_preservation_enabled": None,
        "endpoint_id": "endpoint-1",
        "weight": 128,
    }
    base = {
        "endpoint_configurations": [endpoint],
        "endpoint_group_region": "us-east-1",
    }
    cases = [
        (
            [base, base],
            "Duplicate endpoint group region us-east-1 in endpoint_groups",
        ),
        (
            [dict(base, endpoint_configurations=[endpoint, endpoint])],
            "Duplicate endpoint endpoint-1 in endpoint group us-east-1 endpoint_configurations",
        ),
    ]
    for endpoint_groups, message in cases:
        params = {
            "ip_addresses": None,
            "listeners": [
                {
                    "endpoint_groups": endpoint_groups,
                    "port_ranges": [{"from_port": 443, "to_port": 443}],
                    "protocol": "TCP",
                }
            ],
            "state": "present",
        }
        assert_module_rejects(plugin, params, message)


def endpoint_listeners(*endpoint_ids):
    return [
        {
            "client_affinity": None,
            "endpoint_groups": [endpoint_group_with(*endpoint_ids)],
            "port_ranges": [{"from_port": 443, "to_port": 443}],
            "protocol": "TCP",
        }
    ]


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "endpoint_ids",
    [[EIP_ALLOCATION_ID, EIP_ARN], [EIP_ARN, EIP_ALLOCATION_ID], [INSTANCE_ARN, INSTANCE_ID]],
    ids=["eip-id-then-arn", "eip-arn-then-id", "instance-arn-then-id"],
)
def test_an_ec2_endpoint_named_by_id_and_by_arn_fails_before_any_aws_call(check_mode, endpoint_ids):
    # Live: AWS keeps one endpoint, with the weight of the last entry, for an Elastic IP address given in both forms,
    # so check mode would predict two endpoints and differing weights would never converge.
    module = FakeModule(present_params(endpoint_listeners(*endpoint_ids)), check_mode=check_mode)
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client") as client_factory,
        patch.object(plugin, "ensure_present") as ensure_present,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": f"Duplicate endpoint {endpoint_ids[1]} in endpoint group us-west-2 endpoint_configurations"
    }
    client_factory.assert_not_called()
    ensure_present.assert_not_called()


@pytest.mark.parametrize(
    "endpoint_ids",
    [[EIP_ARN, OTHER_ALLOCATION_ID], [INSTANCE_ARN, EIP_ARN], [INSTANCE_ID, LOAD_BALANCER_ARN]],
    ids=["two-addresses", "instance-and-address", "instance-and-load-balancer"],
)
def test_distinct_ec2_endpoints_are_not_duplicates(endpoint_ids):
    module = FakeModule(present_params(endpoint_listeners(*endpoint_ids)))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


@pytest.mark.parametrize(
    "endpoint_group, message",
    [
        (
            {"endpoint_configurations": [], "endpoint_group_region": ""},
            "endpoint_group_region must not be empty",
        ),
        # Live: CreateEndpointGroup rejects a region " " (InvalidArgumentException), which a real run reaches only
        # after its accelerator and listener writes.
        (
            {"endpoint_configurations": [], "endpoint_group_region": " "},
            "endpoint_group_region must not be empty",
        ),
        (
            {"endpoint_configurations": [], "endpoint_group_region": "\t"},
            "endpoint_group_region must not be empty",
        ),
        (
            {
                "endpoint_configurations": [
                    {
                        "attachment_arn": None,
                        "client_ip_preservation_enabled": None,
                        "endpoint_id": "",
                        "weight": 128,
                    }
                ],
                "endpoint_group_region": "us-east-1",
            },
            "Endpoint group us-east-1 endpoint_id must not be empty",
        ),
        # Live: CreateEndpointGroup rejects an endpoint ID " " (InvalidArgumentException) after the same writes.
        (
            {
                "endpoint_configurations": [
                    {
                        "attachment_arn": None,
                        "client_ip_preservation_enabled": None,
                        "endpoint_id": " ",
                        "weight": 128,
                    }
                ],
                "endpoint_group_region": "us-east-1",
            },
            "Endpoint group us-east-1 endpoint_id must not be empty",
        ),
        (
            {
                "endpoint_configurations": [
                    {
                        "attachment_arn": None,
                        "client_ip_preservation_enabled": None,
                        "endpoint_id": "\t",
                        "weight": 128,
                    }
                ],
                "endpoint_group_region": "us-east-1",
            },
            "Endpoint group us-east-1 endpoint_id must not be empty",
        ),
    ],
    ids=["empty-region", "space-region", "tab-region", "empty-endpoint", "space-endpoint", "tab-endpoint"],
)
def test_empty_required_endpoint_strings_fail_before_any_aws_call(endpoint_group, message):
    # Ansible validates a null required string suboption as "".
    listeners = [
        {
            "client_affinity": None,
            "endpoint_groups": [unset_endpoint_group(**endpoint_group)],
            "port_ranges": [{"from_port": 443, "to_port": 443}],
            "protocol": "TCP",
        }
    ]
    module = FakeModule(present_params(listeners))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client") as client_factory,
        patch.object(plugin, "ensure_present") as ensure_present,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == message
    client_factory.assert_not_called()
    ensure_present.assert_not_called()


def test_endpoint_group_provider_limits_are_rejected():
    base = {
        "endpoint_configurations": [],
        "endpoint_group_region": "us-east-1",
        "health_check_port": None,
        "port_overrides": [],
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    cases = [
        (
            dict(base, endpoint_group_region="r" * 256),
            "endpoint_group_region must contain at most 255 characters",
        ),
        (
            dict(base, health_check_path="not-a-path"),
            "Endpoint group us-east-1 health_check_path must be a valid path of at most 255 characters",
        ),
        (
            dict(base, health_check_path=r"/invalid\path"),
            "Endpoint group us-east-1 health_check_path must be a valid path of at most 255 characters",
        ),
        (
            dict(base, endpoint_configurations=[{}] * 11),
            "Endpoint group us-east-1 endpoint_configurations must contain at most 10 entries",
        ),
        (
            dict(base, port_overrides=[{}] * 11),
            "Endpoint group us-east-1 port_overrides must contain at most 10 entries",
        ),
        (
            dict(base, health_check_port=0),
            "Endpoint group us-east-1 health_check_port must be between 1 and 65535",
        ),
        (
            dict(base, threshold_count=11),
            "Endpoint group us-east-1 threshold_count must be between 1 and 10",
        ),
        (
            dict(base, traffic_dial_percentage=101),
            "Endpoint group us-east-1 traffic_dial_percentage must be between 0 and 100",
        ),
        (
            dict(
                base,
                endpoint_configurations=[{"endpoint_id": "endpoint-1", "weight": 256}],
            ),
            "Endpoint group us-east-1 endpoint_configurations weight must be between 0 and 255",
        ),
        (
            dict(
                base,
                endpoint_configurations=[{"endpoint_id": "e" * 256, "weight": 128}],
            ),
            "Endpoint group us-east-1 endpoint IDs and attachment ARNs must contain at most 255 characters",
        ),
        (
            dict(
                base,
                port_overrides=[{"endpoint_port": 443, "listener_port": 0}],
            ),
            "Endpoint group us-east-1 port_overrides entries must be between 1 and 65535",
        ),
        (
            dict(
                base,
                port_overrides=[
                    {"endpoint_port": 8443, "listener_port": 443},
                    {"endpoint_port": 9443, "listener_port": 443},
                ],
            ),
            "Endpoint group us-east-1 port_overrides listener_port values must be unique",
        ),
        (
            dict(
                base,
                port_overrides=[{"endpoint_port": 8080, "listener_port": 80}],
            ),
            "Endpoint group us-east-1 port_overrides listener_port 80 must be within the listener's port_ranges",
        ),
    ]
    for endpoint_group, message in cases:
        params = {
            "ip_addresses": None,
            "listeners": [
                {
                    "endpoint_groups": [endpoint_group],
                    "port_ranges": [{"from_port": 443, "to_port": 443}],
                }
            ],
            "state": "present",
        }
        assert_module_rejects(plugin, params, message)


def test_endpoint_group_weight_update_sends_attachment():
    client = Mock()
    client.update_endpoint_group.return_value = {
        "EndpointGroup": {
            "EndpointGroupArn": "arn:group",
            "EndpointGroupRegion": "us-east-1",
        }
    }
    module = FakeModule({"purge_endpoint_groups": False})
    desired = {
        "endpoint_configurations": [
            {
                "attachment_arn": "arn:new",
                "client_ip_preservation_enabled": None,
                "endpoint_id": "endpoint-1",
                "weight": 128,
            }
        ],
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    current = {
        "endpoint_descriptions": [
            {
                "endpoint_id": "endpoint-1",
                "weight": 64,
            }
        ],
        "endpoint_group_arn": "arn:group",
        "endpoint_group_region": "us-east-1",
    }
    with patch.object(plugin, "get_endpoint_groups", return_value=[current]):
        changed, groups = plugin.ensure_endpoint_groups(client, module, "arn:listener", [desired])

    assert changed
    assert groups[0]["endpoint_group_arn"] == "arn:group"
    assert client.update_endpoint_group.call_args.kwargs["EndpointConfigurations"] == [
        {
            "AttachmentArn": "arn:new",
            "EndpointId": "endpoint-1",
            "Weight": 128,
        }
    ]


def test_absent_waits_for_prerequisites_when_wait_is_disabled():
    client = Mock()
    module = FakeModule({"wait": False})

    with (
        patch.object(
            plugin,
            "get_accelerator",
            return_value={"AcceleratorArn": "arn:accelerator", "Enabled": True},
        ),
        patch.object(
            plugin,
            "get_listeners",
            return_value=[{"listener_arn": "arn:listener"}],
        ),
        patch.object(plugin, "delete_listener") as delete_listener,
        patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_absent(client, module)

    delete_listener.assert_called_once_with(
        client, module, "arn:accelerator", "arn:listener", changed=False, deadline=ANY
    )
    assert wait_for_accelerator.call_count == 2
    # The listener deletion and both prerequisite waits share one wait_timeout budget.
    deadline = delete_listener.call_args.kwargs["deadline"]
    for call in wait_for_accelerator.call_args_list:
        assert call.args == (client, module, "arn:accelerator", "accelerator_deployed")
        assert call.kwargs == {"changed": True, "deadline": deadline}

    client.delete_accelerator.assert_called_once_with(AcceleratorArn="arn:accelerator", aws_retry=True)


def test_listener_deletion_waits_for_endpoint_group_deletion():
    client = Mock()
    module = FakeModule({})
    with (
        patch.object(
            plugin,
            "get_endpoint_groups",
            return_value=[{"endpoint_group_arn": "arn:group"}],
        ),
        patch.object(plugin, "delete_endpoint_group") as delete_endpoint_group,
        patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
        patch.object(plugin, "require_client_methods") as require,
    ):
        plugin.delete_listener(client, module, "arn:accelerator", "arn:listener")

    delete_endpoint_group.assert_called_once_with(client, module, "arn:group", changed=False)
    wait_for_accelerator.assert_called_once_with(
        client, module, "arn:accelerator", "accelerator_deployed", changed=True, deadline=ANY
    )
    client.delete_listener.assert_called_once_with(ListenerArn="arn:listener", aws_retry=True)
    require.assert_called_once_with(
        module,
        client,
        "Global Accelerator",
        {"delete_listener": ("ListenerArn",)},
        changed=False,
    )


def test_listener_creation_waits_before_endpoint_groups():
    client = Mock()
    client.create_listener.return_value = {
        "Listener": {
            "ClientAffinity": "NONE",
            "ListenerArn": "arn:listener",
            "PortRanges": [{"FromPort": 443, "ToPort": 443}],
            "Protocol": "TCP",
        }
    }
    desired = {
        "client_affinity": "NONE",
        "endpoint_groups": [{"endpoint_group_region": "us-east-1"}],
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    module = FakeModule({"purge_listeners": True})
    with (
        patch.object(
            plugin,
            "reconcile_listeners",
            return_value=([], [], [desired], []),
        ),
        patch.object(plugin, "get_listeners", return_value=[]),
        patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
        patch.object(plugin, "ensure_endpoint_groups", return_value=(False, [])),
        patch.object(plugin, "require_client_methods"),
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator")

    wait_for_accelerator.assert_called_once_with(
        client, module, "arn:accelerator", "accelerator_deployed", changed=True, deadline=ANY
    )


def test_listener_replacement_retries_after_freeing_quota():
    client = Mock()
    client.create_listener.side_effect = [
        plugin.ClientError(
            {"Error": {"Code": "LimitExceededException", "Message": "full"}},
            "CreateListener",
        ),
        {
            "Listener": {
                "ClientAffinity": "NONE",
                "ListenerArn": "arn:new",
                "PortRanges": [{"FromPort": 443, "ToPort": 443}],
                "Protocol": "TCP",
            }
        },
    ]
    desired = {
        "client_affinity": "NONE",
        "endpoint_groups": None,
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    current = {
        "client_affinity": "NONE",
        "listener_arn": "arn:old",
        "port_ranges": [{"from_port": 80, "to_port": 80}],
        "protocol": "TCP",
    }
    module = FakeModule({"purge_listeners": True})
    with (
        patch.object(
            plugin,
            "reconcile_listeners",
            return_value=([], [], [desired], [current]),
        ),
        patch.object(plugin, "get_listeners", return_value=[current]),
        patch.object(plugin, "delete_listener") as delete_listener,
        patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
        patch.object(plugin, "require_client_methods"),
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    assert listeners[0]["listener_arn"] == "arn:new"
    assert client.create_listener.call_count == 2
    first, second = client.create_listener.call_args_list
    assert first.kwargs["IdempotencyToken"] == second.kwargs["IdempotencyToken"]
    delete_listener.assert_called_once_with(client, module, "arn:accelerator", "arn:old", changed=False, deadline=ANY)
    wait_for_accelerator.assert_called_once_with(
        client, module, "arn:accelerator", "accelerator_deployed", changed=True, deadline=ANY
    )


def test_accelerator_creation_waits_before_listeners():
    client = Mock()
    client.create_accelerator.return_value = {
        "Accelerator": {
            "AcceleratorArn": "arn:accelerator",
            "Enabled": True,
            "IpAddressType": "IPV4",
            "Name": "example",
        }
    }
    module = FakeModule(
        {
            "enabled": True,
            "idempotency_token": None,
            "ip_addresses": None,
            "ip_address_type": "IPV4",
            "listeners": [{"client_affinity": None, "endpoint_groups": None}],
            "name": "example",
            "purge_listeners": True,
            "purge_tags": True,
            "tags": None,
            "wait": False,
        }
    )
    with (
        patch.object(plugin, "get_accelerator", return_value=None),
        patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
        patch.object(plugin, "ensure_listeners", return_value=(True, [])),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait_for_accelerator.assert_called_once_with(
        client, module, "arn:accelerator", "accelerator_deployed", changed=True, deadline=ANY
    )
    assert require.call_args.args[3] == {
        "create_accelerator": (
            "Enabled",
            "IdempotencyToken",
            "IpAddressType",
            "Name",
        )
    }


def created_listener_response(**request):
    return {
        "Listener": {
            "ClientAffinity": "NONE",
            "ListenerArn": "arn:listener",
            "PortRanges": request["PortRanges"],
            "Protocol": request["Protocol"],
        }
    }


def test_listener_creates_with_identical_inputs_use_unique_tokens():
    client = Mock()
    client.create_listener.side_effect = created_listener_response
    module = FakeModule({"listeners": [review_desired(443, 443)], "purge_listeners": True})
    with (
        patch.object(plugin, "get_listeners", return_value=[]),
        patch.object(plugin, "wait_for_accelerator"),
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator")
        plugin.ensure_listeners(client, module, "arn:accelerator")

    first, second = client.create_listener.call_args_list
    assert first.kwargs["IdempotencyToken"] != second.kwargs["IdempotencyToken"]


def test_listener_create_retries_reuse_the_token():
    raw_client = Mock()
    raw_client.create_listener.side_effect = [
        plugin.ClientError({"Error": {"Code": "Throttling", "Message": "slow down"}}, "CreateListener"),
        created_listener_response(PortRanges=[{"FromPort": 443, "ToPort": 443}], Protocol="TCP"),
    ]
    client = RetryingBotoClientWrapper(raw_client, plugin.AWSRetry.jittered_backoff(delay=0))
    module = FakeModule({"listeners": [review_desired(443, 443)], "purge_listeners": True})
    with (
        patch.object(plugin, "get_listeners", return_value=[]),
        patch.object(plugin, "wait_for_accelerator"),
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator")

    first, second = raw_client.create_listener.call_args_list
    assert first.kwargs["IdempotencyToken"] == second.kwargs["IdempotencyToken"]


def test_listener_writes_release_conflicts_then_update_then_create_with_one_token_each():
    def listener(arn, protocol, port, affinity="NONE"):
        return {
            "client_affinity": affinity,
            "listener_arn": arn,
            "port_ranges": [{"from_port": port, "to_port": port}],
            "protocol": protocol,
        }

    def wanted(protocol, start, end, affinity=None):
        return {
            "client_affinity": affinity,
            "endpoint_groups": None,
            "port_ranges": [{"from_port": start, "to_port": end}],
            "protocol": protocol,
        }

    current = [
        listener("arn:a", "TCP", 80),
        listener("arn:b", "TCP", 81),
        listener("arn:c", "UDP", 53, "SOURCE_IP"),
        listener("arn:d", "TCP", 9000),
    ]
    desired = [
        wanted("TCP", 80, 81),
        wanted("UDP", 53, 54),
        wanted("UDP", 500, 500, "SOURCE_IP"),
        wanted("UDP", 4500, 4500),
    ]
    events = []
    quota_errors = [
        plugin.ClientError({"Error": {"Code": "LimitExceededException", "Message": "full"}}, "CreateListener")
    ]

    def update(**request):
        events.append(("update_listener", request))
        return {"Listener": request}

    def create(**request):
        events.append(("create_listener", request))
        if request["PortRanges"][0]["FromPort"] == 4500 and quota_errors:
            raise quota_errors.pop()

        return {"Listener": dict(request, ClientAffinity=request.get("ClientAffinity", "NONE"), ListenerArn="arn:new")}

    client = Mock()
    client.update_listener.side_effect = update
    client.create_listener.side_effect = create
    module = FakeModule({"listeners": desired, "purge_listeners": True})
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "delete_listener", side_effect=lambda c, m, a, arn, **kw: events.append(("delete", arn))),
        patch.object(plugin, "wait_for_accelerator", side_effect=lambda *args, **kwargs: events.append(("wait",))),
        patch.object(plugin.uuid, "uuid4", side_effect=["token-0", "token-1"]) as uuid4,
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    assert uuid4.call_count == 2
    udp_4500 = {
        "AcceleratorArn": "arn:accelerator",
        "IdempotencyToken": "token-1",
        "PortRanges": [{"FromPort": 4500, "ToPort": 4500}],
        "Protocol": "UDP",
        "aws_retry": True,
    }
    assert events == [
        # The obsolete listener holding a desired port goes first; the unrelated one only when the quota needs it.
        ("delete", "arn:b"),
        ("wait",),
        (
            "update_listener",
            {
                "ClientAffinity": "NONE",
                "ListenerArn": "arn:a",
                "PortRanges": [{"FromPort": 80, "ToPort": 81}],
                "Protocol": "TCP",
                "aws_retry": True,
            },
        ),
        (
            "update_listener",
            {
                "ClientAffinity": "SOURCE_IP",
                "ListenerArn": "arn:c",
                "PortRanges": [{"FromPort": 53, "ToPort": 54}],
                "Protocol": "UDP",
                "aws_retry": True,
            },
        ),
        (
            "create_listener",
            {
                "AcceleratorArn": "arn:accelerator",
                "ClientAffinity": "SOURCE_IP",
                "IdempotencyToken": "token-0",
                "PortRanges": [{"FromPort": 500, "ToPort": 500}],
                "Protocol": "UDP",
                "aws_retry": True,
            },
        ),
        ("create_listener", udp_4500),
        ("delete", "arn:d"),
        ("wait",),
        ("create_listener", udp_4500),
    ]
    assert [(item["protocol"], item["client_affinity"]) for item in listeners] == [
        ("TCP", "NONE"),
        ("UDP", "SOURCE_IP"),
        ("UDP", "SOURCE_IP"),
        ("UDP", "NONE"),
    ]


def test_endpoint_group_creates_with_identical_inputs_use_unique_tokens():
    client = Mock()
    client.create_endpoint_group.return_value = {
        "EndpointGroup": {
            "EndpointGroupArn": "arn:group",
            "EndpointGroupRegion": "us-east-1",
        }
    }
    module = FakeModule({"purge_endpoint_groups": False})
    desired = {
        "endpoint_configurations": None,
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    with patch.object(plugin, "get_endpoint_groups", return_value=[]):
        plugin.ensure_endpoint_groups(client, module, "arn:listener", [desired])
        plugin.ensure_endpoint_groups(client, module, "arn:listener", [desired])

    first, second = client.create_endpoint_group.call_args_list
    assert first.kwargs["IdempotencyToken"] != second.kwargs["IdempotencyToken"]


def test_accelerator_creates_with_identical_inputs_use_unique_tokens():
    client = Mock()
    client.create_accelerator.return_value = {
        "Accelerator": {
            "AcceleratorArn": "arn:accelerator",
            "Enabled": True,
            "IpAddressType": "IPV4",
            "Name": "example",
        }
    }
    module = FakeModule(
        {
            "enabled": None,
            "idempotency_token": None,
            "ip_address_type": None,
            "ip_addresses": None,
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        }
    )
    with (
        patch.object(plugin, "get_accelerator", return_value=None),
        patch.object(plugin, "require_client_methods"),
    ):
        for _attempt in range(2):
            with pytest.raises(ModuleExit):
                plugin.ensure_present(client, module)

    first, second = client.create_accelerator.call_args_list
    assert first.kwargs["IdempotencyToken"] != second.kwargs["IdempotencyToken"]


def review_listener(arn, start, end):
    return {
        "listener_arn": arn,
        "protocol": "TCP",
        "client_affinity": "NONE",
        "port_ranges": [{"from_port": start, "to_port": end}],
    }


def review_desired(start, end):
    return {
        "protocol": "TCP",
        "client_affinity": "NONE",
        "endpoint_groups": None,
        "port_ranges": [{"from_port": start, "to_port": end}],
    }


@pytest.mark.parametrize("check_mode", [False, True])
def test_listener_updates_release_ports_before_dependent_expansion(check_mode):
    current = [review_listener("arn:a", 90, 90), review_listener("arn:b", 80, 81)]
    desired = [review_desired(81, 90), review_desired(80, 80)]
    module = FakeModule({"listeners": desired, "purge_listeners": True}, check_mode=check_mode)
    client = Mock()
    active = {item["listener_arn"]: item for item in current}
    events = []
    pending = {}

    def update(**request):
        arn = request["ListenerArn"]
        target = review_listener(arn, request["PortRanges"][0]["FromPort"], request["PortRanges"][0]["ToPort"])
        assert not any(plugin.listeners_overlap(target, other) for key, other in active.items() if key != arn)
        pending[arn] = target
        events.append(arn)
        return {
            "Listener": {
                "ClientAffinity": request["ClientAffinity"],
                "ListenerArn": arn,
                "PortRanges": request["PortRanges"],
                "Protocol": request["Protocol"],
            }
        }

    def wait(*args, **kwargs):
        active.update(pending)
        pending.clear()
        events.append("wait")

    client.update_listener.side_effect = update
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_accelerator", side_effect=wait),
        patch.object(plugin, "delete_listener") as delete,
    ):
        changed, result = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    assert len(result) == 2
    assert events == ([] if check_mode else ["arn:b", "wait", "arn:a"])
    delete.assert_not_called()


@pytest.mark.parametrize("operation", ["update_listener", "create_listener", "delete_listener"])
def test_listener_preflight_failure_does_not_update_the_accelerator(operation):
    listener = {"client_affinity": None, "endpoint_groups": None}
    module = FakeModule(accelerator_params(enabled=False, listeners=[listener]))
    client = Mock()

    def require(module, client, service, methods, changed=False):
        if operation in methods:
            module.fail_json(changed=changed, msg="Unsupported listener write")

    with (
        patch.object(plugin, "get_accelerator", return_value=deployed_accelerator()),
        patch.object(plugin, "require_client_methods", side_effect=require),
        patch.object(plugin, "ensure_listeners") as ensure_listeners,
        pytest.raises(ModuleFail, match="Unsupported listener write") as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.update_accelerator.assert_not_called()
    ensure_listeners.assert_not_called()


@pytest.mark.parametrize(
    ("listeners", "purge_listeners", "expected"),
    [
        ([], False, {}),
        (
            [{"client_affinity": None}],
            False,
            {
                "create_listener": ("AcceleratorArn", "IdempotencyToken", "PortRanges", "Protocol"),
                "update_listener": ("ClientAffinity", "ListenerArn", "PortRanges", "Protocol"),
            },
        ),
        (
            [{"client_affinity": "SOURCE_IP"}],
            True,
            {
                "create_listener": ("AcceleratorArn", "ClientAffinity", "IdempotencyToken", "PortRanges", "Protocol"),
                "delete_endpoint_group": ("EndpointGroupArn",),
                "delete_listener": ("ListenerArn",),
                "update_listener": ("ClientAffinity", "ListenerArn", "PortRanges", "Protocol"),
            },
        ),
    ],
)
def test_listener_writes_are_checked_for_every_possible_change(listeners, purge_listeners, expected):
    module = FakeModule({"listeners": listeners, "purge_listeners": purge_listeners})
    client = Mock()
    with patch.object(plugin, "require_client_methods") as require:
        plugin.require_listener_writes(module, client)

    if expected:
        require.assert_called_once_with(module, client, "Global Accelerator", expected)
    else:
        require.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("arns", [("arn:a", "arn:b"), ("arn:b", "arn:a")])
def test_circular_listener_dependencies_fail_before_mutation(check_mode, arns):
    # Each entry shares a port with both listeners, so every pairing needs a port the other listener still holds.
    current = listed_listeners({arns[0]: (80, 81), arns[1]: (82, 83)})
    split = dict(
        review_desired(80, 80), port_ranges=[{"from_port": 80, "to_port": 80}, {"from_port": 83, "to_port": 83}]
    )
    desired = [review_desired(81, 82), split]
    module = FakeModule(
        {"listeners": desired, "purge_endpoint_groups": True, "purge_listeners": True}, check_mode=check_mode
    )
    client = Mock()
    with (
        patch.object(plugin, "get_listeners", return_value=current),
        patch.object(plugin, "delete_listener") as delete,
        pytest.raises(ModuleFail, match="circular port dependencies") as raised,
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator")

    assert raised.value.values["changed"] is False
    delete.assert_not_called()
    client.update_listener.assert_not_called()
    client.create_listener.assert_not_called()


@pytest.mark.parametrize("wait, check_mode", [(True, False), (False, False), (True, True), (False, True)])
def test_unchanged_accelerator_waits_for_requested_readiness(wait, check_mode):
    module = FakeModule(
        {
            "enabled": True,
            "ip_address_type": "IPV4",
            "ip_addresses": None,
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": wait,
        },
        check_mode=check_mode,
    )
    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "Name": "example",
        "Status": "IN_PROGRESS",
    }
    client = Mock()
    with (
        patch.object(plugin, "get_accelerator", side_effect=[current, dict(current, Status="DEPLOYED")]) as read,
        patch.object(plugin, "wait_for_accelerator") as waiter,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    should_wait = wait and not check_mode
    assert result.value.values["changed"] is False
    # Check mode predicts the status a real run returns after its wait.
    assert result.value.values["accelerator"]["status"] == ("DEPLOYED" if wait else "IN_PROGRESS")
    assert read.call_count == (2 if should_wait else 1)
    if should_wait:
        waiter.assert_called_once_with(client, module, "arn:accelerator", "accelerator_deployed", deadline=ANY)
    else:
        waiter.assert_not_called()

    client.update_accelerator.assert_not_called()
    client.create_accelerator.assert_not_called()


@pytest.mark.parametrize(
    "overrides, status",
    [
        # A real run waits for a deploying accelerator before any change, and checks it again.
        ({"tags": {"team": "edge"}}, "DEPLOYED"),
        ({"tags": {"team": "edge"}, "wait": True}, "DEPLOYED"),
        ({"listeners": []}, "DEPLOYED"),
        ({"name": "renamed", "wait": True}, "DEPLOYED"),
        # Without a wait, a real run returns the UpdateAccelerator response, which live reports IN_PROGRESS.
        ({"name": "renamed"}, "IN_PROGRESS"),
        # Nothing to change and no wait requested: a real run returns the observed status.
        ({}, "IN_PROGRESS"),
    ],
)
def test_check_mode_predicts_the_status_a_real_run_returns_for_a_deploying_accelerator(overrides, status):
    module = FakeModule(accelerator_params(**overrides), check_mode=True)
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "get_accelerator", return_value=deployed_accelerator(Status="IN_PROGRESS")) as read,
        patch.object(plugin, "get_listeners", return_value=[]),
        patch.object(plugin, "wait_for_accelerator") as waiter,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["accelerator"]["status"] == status
    read.assert_called_once()
    waiter.assert_not_called()
    assert [name for name, unused_args, unused_kwargs in client.mock_calls] == (
        ["list_tags_for_resource"] if "tags" in overrides else []
    )


@pytest.mark.parametrize("wait, status", [(True, "DEPLOYED"), (False, "IN_PROGRESS")])
def test_check_mode_create_predicts_the_status_a_real_run_returns(wait, status):
    module = FakeModule(accelerator_params(wait=wait), check_mode=True)
    client = Mock()
    with (
        patch.object(plugin, "get_accelerator", return_value=None),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    assert result.value.values["accelerator"]["status"] == status
    assert client.mock_calls == []


@pytest.mark.parametrize("wait, status", [(True, "DEPLOYED"), (False, "IN_PROGRESS")])
def test_check_mode_update_predicts_the_status_a_real_run_returns(wait, status):
    # Without a wait, a real run returns the UpdateAccelerator response, which live reports IN_PROGRESS.
    module = FakeModule(accelerator_params(name="renamed", wait=wait), check_mode=True)
    client = Mock()
    with (
        patch.object(plugin, "get_accelerator", return_value=deployed_accelerator()),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    assert result.value.values["accelerator"]["name"] == "renamed"
    assert result.value.values["accelerator"]["status"] == status
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("family", ["IPV4", "DUAL_STACK"])
@pytest.mark.parametrize("addresses", [["192.0.2.1"], ["192.0.2.1", "192.0.2.2"]])
def test_requested_addresses_ignore_additional_assigned_addresses(check_mode, family, addresses):
    module = FakeModule(
        {
            "enabled": True,
            "ip_address_type": family,
            "ip_addresses": addresses,
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        },
        check_mode=check_mode,
    )
    ip_sets = [{"IpFamily": "IPv4", "IpAddresses": ["192.0.2.1", "192.0.2.2"]}]
    if family == "DUAL_STACK":
        ip_sets.append({"IpFamily": "IPv6", "IpAddresses": ["2001:db8::1", "2001:db8::2"]})

    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": family,
        "IpSets": ip_sets,
        "Name": "example",
        "Status": "DEPLOYED",
    }
    client = Mock()
    client.update_accelerator.return_value = {"Accelerator": current}
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is False
    assert [item["ip_addresses"] for item in result.value.values["accelerator"]["ip_sets"]] == [
        item["IpAddresses"] for item in ip_sets
    ]
    client.update_accelerator.assert_not_called()
    client.create_accelerator.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("status", ["DEPLOYED", "IN_PROGRESS"])
@pytest.mark.parametrize("addresses", [["192.0.2.3"], ["192.0.2.1", "192.0.2.3"]])
def test_changed_ip_addresses_fail_before_modifying_an_existing_accelerator(check_mode, status, addresses):
    module = FakeModule(
        {
            "enabled": False,
            "ip_address_type": "IPV4",
            "ip_addresses": addresses,
            "listeners": [],
            "name": "renamed",
            "purge_tags": True,
            "tags": {"Environment": "test"},
            "wait": True,
        },
        check_mode=check_mode,
    )
    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "IpSets": [{"IpFamily": "IPv4", "IpAddresses": ["192.0.2.1", "192.0.2.2"]}],
        "Name": "example",
        "Status": status,
    }
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_accelerator") as waiter,
        patch.object(plugin, "ensure_listeners") as listeners,
        patch.object(plugin, "reconcile_arn_tags") as tagger,
        pytest.raises(ModuleFail) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["msg"] == (
        "ip_addresses cannot be changed for existing AWS Global Accelerator arn:accelerator. "
        "The existing accelerator has not been modified."
    )
    waiter.assert_not_called()
    listeners.assert_not_called()
    tagger.assert_not_called()
    client.update_accelerator.assert_not_called()
    client.create_accelerator.assert_not_called()
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


def test_update_never_sends_ip_addresses():
    module = FakeModule(
        {
            "enabled": False,
            "ip_address_type": "IPV4",
            "ip_addresses": ["192.0.2.1"],
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "IpSets": [{"IpFamily": "IPv4", "IpAddresses": ["192.0.2.1", "192.0.2.2"]}],
        "Name": "example",
        "Status": "DEPLOYED",
    }
    client = Mock()
    client.update_accelerator.return_value = {"Accelerator": dict(current, Enabled=False)}
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    client.update_accelerator.assert_called_once_with(
        AcceleratorArn="arn:accelerator",
        Enabled=False,
        IpAddressType="IPV4",
        Name="example",
        aws_retry=True,
    )
    require.assert_called_once_with(
        module,
        client,
        "Global Accelerator",
        {"update_accelerator": ("AcceleratorArn", "Enabled", "IpAddressType", "Name")},
    )


def test_create_sends_ip_addresses():
    module = FakeModule(
        {
            "enabled": None,
            "idempotency_token": "token",
            "ip_address_type": None,
            "ip_addresses": ["192.0.2.1"],
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        }
    )
    created = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "IpSets": [{"IpFamily": "IPv4", "IpAddresses": ["192.0.2.1", "198.51.100.1"]}],
        "Name": "example",
        "Status": "IN_PROGRESS",
    }
    client = Mock()
    client.create_accelerator.return_value = {"Accelerator": created}
    with (
        patch.object(plugin, "get_accelerator", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    client.create_accelerator.assert_called_once_with(
        IdempotencyToken="token",
        IpAddresses=["192.0.2.1"],
        Name="example",
        aws_retry=True,
    )


def test_client_retries_only_transient_accelerator_transactions():
    module = Mock(params={"name": "example", "state": "absent", "tags": None})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "AWSRetry") as retry,
        patch.object(plugin, "ensure_absent"),
        patch.object(plugin, "require_positive_wait_bounds"),
    ):
        plugin.main()

    retry.jittered_backoff.assert_called_once_with(catch_extra_error_codes=["TransactionInProgressException"])


@pytest.mark.parametrize("family", ["IPV4", "DUAL_STACK"])
@pytest.mark.parametrize("addresses", [["192.0.2.1"], ["192.0.2.1", "192.0.2.2"]])
def test_check_mode_enabled_change_preserves_matching_ip_sets(family, addresses):
    ip_sets = [{"IpFamily": "IPv4", "IpAddresses": ["192.0.2.1", "192.0.2.2"]}]
    if family == "DUAL_STACK":
        ip_sets.append({"IpFamily": "IPv6", "IpAddresses": ["2001:db8::1", "2001:db8::2"]})

    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": family,
        "IpSets": ip_sets,
        "Name": "example",
        "Status": "DEPLOYED",
    }
    module = FakeModule(
        {
            "enabled": False,
            "ip_address_type": family,
            "ip_addresses": addresses,
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        },
        check_mode=True,
    )
    client = Mock()
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    assert result.value.values["accelerator"]["enabled"] is False
    assert result.value.values["accelerator"]["ip_sets"] == [
        {"ip_family": item["IpFamily"], "ip_addresses": item["IpAddresses"]} for item in ip_sets
    ]
    assert current["Enabled"] is True
    assert client.mock_calls == []


@pytest.mark.parametrize("wait, status", [(True, "DEPLOYED"), (False, "IN_PROGRESS")])
@pytest.mark.parametrize("family_keys", [("IpAddressFamily", "IpFamily"), ("IpAddressFamily",), ("IpFamily",)])
def test_check_mode_change_to_ipv4_drops_the_dual_stack_name_and_ipv6_addresses(wait, status, family_keys):
    # Live: the UpdateAccelerator response and the deployed accelerator both omit DualStackDnsName and the IPv6 set.
    def ip_set(family, addresses):
        return dict({key: family for key in family_keys}, IpAddresses=addresses)

    current = deployed_accelerator(
        DnsName="a1234567890abcdef.awsglobalaccelerator.com",
        DualStackDnsName="a1234567890abcdef.dualstack.awsglobalaccelerator.com",
        Enabled=False,
        IpAddressType="DUAL_STACK",
        IpSets=[ip_set("IPv4", ["192.0.2.1", "192.0.2.2"]), ip_set("IPv6", ["2001:db8::1", "2001:db8::2"])],
    )
    module = FakeModule(accelerator_params(ip_address_type="IPV4", wait=wait), check_mode=True)
    client = Mock()
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    accelerator = result.value.values["accelerator"]
    assert result.value.values["changed"] is True
    assert accelerator["dns_name"] == "a1234567890abcdef.awsglobalaccelerator.com"
    assert "dual_stack_dns_name" not in accelerator
    assert accelerator["ip_address_type"] == "IPV4"
    returned_keys = {"IpAddressFamily": "ip_address_family", "IpFamily": "ip_family"}
    assert accelerator["ip_sets"] == [
        dict({returned_keys[key]: "IPv4" for key in family_keys}, ip_addresses=["192.0.2.1", "192.0.2.2"])
    ]
    assert accelerator["status"] == status
    assert current["IpAddressType"] == "DUAL_STACK"
    assert "DualStackDnsName" in current
    assert len(current["IpSets"]) == 2
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [False, True])
def test_matching_cross_account_endpoint_is_unchanged(check_mode):
    current = {
        "endpoint_group_arn": "arn:group",
        "endpoint_group_region": "us-east-1",
        "endpoint_descriptions": [{"endpoint_id": "endpoint-1", "weight": 128, "client_ip_preservation_enabled": True}],
    }
    desired = {
        "endpoint_group_region": "us-east-1",
        "endpoint_configurations": [
            {
                "endpoint_id": "endpoint-1",
                "weight": 128,
                "client_ip_preservation_enabled": True,
                "attachment_arn": "arn:attachment",
            }
        ],
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "threshold_count": None,
        "traffic_dial_percentage": None,
        "port_overrides": None,
    }
    client = Mock()
    module = FakeModule({"purge_endpoint_groups": True}, check_mode=check_mode)
    with patch.object(plugin, "get_endpoint_groups", return_value=[current]):
        changed, groups = plugin.ensure_endpoint_groups(client, module, "arn:listener", [desired])

    assert changed is False
    assert groups == [current]
    assert client.mock_calls == []


def test_settings_that_change_existing_accelerators_have_no_module_defaults():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleExit({})

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleExit):
        plugin.main()

    spec = captured["argument_spec"]
    assert "default" not in spec["enabled"]
    assert "default" not in spec["ip_address_type"]
    assert "default" not in spec["listeners"]["options"]["client_affinity"]


@pytest.mark.parametrize("check_mode", [False, True])
def test_omitted_settings_leave_an_existing_accelerator_unchanged(check_mode):
    module = FakeModule(
        {
            "enabled": None,
            "ip_address_type": None,
            "ip_addresses": None,
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        },
        check_mode=check_mode,
    )
    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": False,
        "IpAddressType": "DUAL_STACK",
        "Name": "example",
        "Status": "DEPLOYED",
    }
    client = Mock()
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is False
    assert result.value.values["accelerator"]["enabled"] is False
    assert result.value.values["accelerator"]["ip_address_type"] == "DUAL_STACK"
    client.update_accelerator.assert_not_called()


def test_supplied_setting_updates_only_that_setting():
    module = FakeModule(
        {
            "enabled": True,
            "ip_address_type": None,
            "ip_addresses": None,
            "listeners": None,
            "name": "example",
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": False,
        "IpAddressType": "DUAL_STACK",
        "Name": "example",
        "Status": "DEPLOYED",
    }
    client = Mock()
    client.update_accelerator.return_value = {"Accelerator": dict(current, Enabled=True)}
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    client.update_accelerator.assert_called_once_with(
        AcceleratorArn="arn:accelerator", Enabled=True, Name="example", aws_retry=True
    )


def test_omitted_client_affinity_keeps_the_existing_listener_setting():
    current = [
        {
            "client_affinity": "SOURCE_IP",
            "listener_arn": "arn:listener",
            "port_ranges": [{"from_port": 80, "to_port": 80}],
            "protocol": "TCP",
        }
    ]
    desired = {"client_affinity": None, "endpoint_groups": None, "protocol": "TCP"}
    module = Mock(
        params={
            "listeners": [dict(desired, port_ranges=[{"from_port": 80, "to_port": 80}])],
            "purge_listeners": True,
        }
    )
    matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)
    assert [item[0] for item in matched] == current
    assert updates == creates == deletes == []


def test_listener_update_keeps_current_client_affinity_and_returns_the_response():
    current = {
        "client_affinity": "SOURCE_IP",
        "listener_arn": "arn:listener",
        "port_ranges": [{"from_port": 80, "to_port": 80}],
        "protocol": "TCP",
    }
    desired = {
        "client_affinity": None,
        "endpoint_groups": None,
        "port_ranges": [{"from_port": 443, "to_port": 443}],
        "protocol": "TCP",
    }
    client = Mock()
    client.update_listener.return_value = {
        "Listener": {
            "ClientAffinity": "SOURCE_IP",
            "ListenerArn": "arn:listener",
            "PortRanges": [{"FromPort": 443, "ToPort": 443}],
            "Protocol": "TCP",
        }
    }
    module = FakeModule({"listeners": [desired], "purge_listeners": True})
    with (
        patch.object(plugin, "get_listeners", return_value=[current]),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_accelerator"),
    ):
        changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

    assert changed
    client.update_listener.assert_called_once_with(
        ClientAffinity="SOURCE_IP",
        ListenerArn="arn:listener",
        PortRanges=[{"FromPort": 443, "ToPort": 443}],
        Protocol="TCP",
        aws_retry=True,
    )
    assert listeners == [
        {
            "client_affinity": "SOURCE_IP",
            "listener_arn": "arn:listener",
            "port_ranges": [{"from_port": 443, "to_port": 443}],
            "protocol": "TCP",
        }
    ]


def test_listener_update_rejects_a_malformed_response_as_changed():
    current = review_listener("arn:a", 80, 80)
    client = Mock()
    client.update_listener.return_value = {}
    module = FakeModule({"listeners": [review_desired(443, 443)], "purge_listeners": True})
    with (
        patch.object(plugin, "get_listeners", return_value=[current]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator")

    assert raised.value.values == {"changed": True, "msg": "Global Accelerator returned an invalid listener"}


@pytest.mark.parametrize("mutated", [False, True])
def test_listener_update_failure_reports_earlier_changes(mutated):
    current = review_listener("arn:a", 80, 80)
    client = Mock()
    client.update_listener.side_effect = plugin.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "UpdateListener"
    )
    module = FakeModule({"listeners": [review_desired(443, 443)], "purge_listeners": True})
    with (
        patch.object(plugin, "get_listeners", return_value=[current]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_listeners(client, module, "arn:accelerator", mutated=mutated)

    assert raised.value.values["changed"] is mutated


def test_absent_disable_failure_after_listener_deletion_reports_changed():
    client = Mock()
    client.update_accelerator.side_effect = plugin.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "UpdateAccelerator"
    )
    module = FakeModule({"wait": False})
    with (
        patch.object(
            plugin,
            "get_accelerator",
            return_value={"AcceleratorArn": "arn:accelerator", "Enabled": True},
        ),
        patch.object(plugin, "get_listeners", return_value=[{"listener_arn": "arn:listener"}]),
        patch.object(plugin, "delete_listener"),
        patch.object(plugin, "wait_for_accelerator"),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is True


def test_absent_disable_failure_without_earlier_changes_reports_unchanged():
    client = Mock()
    client.update_accelerator.side_effect = plugin.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "UpdateAccelerator"
    )
    module = FakeModule({"wait": False})
    with (
        patch.object(
            plugin,
            "get_accelerator",
            return_value={"AcceleratorArn": "arn:accelerator", "Enabled": True},
        ),
        patch.object(plugin, "get_listeners", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False


def test_listener_deletion_failure_after_endpoint_group_deletion_reports_changed():
    client = Mock()
    client.delete_listener.side_effect = plugin.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "DeleteListener"
    )
    module = FakeModule({})
    with (
        patch.object(plugin, "get_endpoint_groups", return_value=[{"endpoint_group_arn": "arn:group"}]),
        patch.object(plugin, "delete_endpoint_group"),
        patch.object(plugin, "wait_for_accelerator"),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.delete_listener(client, module, "arn:accelerator", "arn:listener")

    assert raised.value.values["changed"] is True


def test_deployment_wait_failure_after_create_reports_changed():
    client = Mock()
    client.create_accelerator.return_value = {
        "Accelerator": {
            "AcceleratorArn": "arn:accelerator",
            "Enabled": True,
            "IpAddressType": "IPV4",
            "Name": "example",
        }
    }
    module = FakeModule(
        {
            "enabled": True,
            "idempotency_token": None,
            "ip_addresses": None,
            "ip_address_type": "IPV4",
            "listeners": None,
            "name": "example",
            "purge_tags": True,
            "tags": None,
            "wait": True,
            "wait_delay": 1,
            "wait_timeout": 1,
        }
    )
    waiter = Mock()
    waiter.wait.side_effect = WaiterError("accelerator_deployed", "timeout", {})
    with (
        patch.object(plugin, "get_accelerator", return_value=None),
        patch.object(plugin, "require_client_methods"),
        patch("ansible_collections.linuxhq.aws.plugins.module_utils.wait.build_waiter_factory") as factory,
        pytest.raises(ModuleFail) as raised,
    ):
        factory.return_value.get_waiter.return_value = waiter
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True


def accelerator_params(**overrides):
    params = {
        "arn": None,
        "enabled": None,
        "idempotency_token": None,
        "ip_address_type": None,
        "ip_addresses": None,
        "listeners": None,
        "name": "example",
        "purge_endpoint_groups": True,
        "purge_listeners": True,
        "purge_tags": True,
        "tags": None,
        "wait": False,
    }
    params.update(overrides)
    return params


def deployed_accelerator(**overrides):
    accelerator = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "Name": "example",
        "Status": "DEPLOYED",
    }
    accelerator.update(overrides)
    return accelerator


@pytest.mark.parametrize("listeners_changed", [True, False])
def test_tag_failure_reports_whether_listeners_were_changed(listeners_changed):
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": []}
    client.tag_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServiceErrorException", "Message": "failed"}}, "TagResource"
    )
    module = FakeModule(accelerator_params(listeners=[], tags={"Env": "test"}))
    with (
        patch.object(plugin, "get_accelerator", return_value=deployed_accelerator()),
        patch.object(plugin, "ensure_listeners", return_value=(listeners_changed, [])),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Unable to tag AWS Global Accelerator arn:accelerator"
    assert raised.value.values["changed"] is listeners_changed


def test_unsupported_endpoint_group_write_fails_before_updating_the_accelerator():
    endpoint_group = {
        "endpoint_configurations": None,
        "endpoint_group_region": "us-east-1",
        "health_check_interval_seconds": None,
        "health_check_path": None,
        "health_check_port": None,
        "health_check_protocol": None,
        "port_overrides": [{"endpoint_port": 8443, "listener_port": 443}],
        "threshold_count": None,
        "traffic_dial_percentage": None,
    }
    listener = {"client_affinity": None, "endpoint_groups": [endpoint_group]}
    module = FakeModule(accelerator_params(enabled=False, listeners=[listener]))
    client = Mock()

    def require(module, client, service, methods, changed=False):
        if "create_endpoint_group" in methods:
            assert "PortOverrides" in methods["create_endpoint_group"]
            module.fail_json(changed=changed, msg="Unsupported endpoint group write")

    with (
        patch.object(plugin, "get_accelerator", return_value=deployed_accelerator()),
        patch.object(plugin, "require_client_methods", side_effect=require),
        patch.object(plugin, "ensure_listeners") as ensure_listeners,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.update_accelerator.assert_not_called()
    ensure_listeners.assert_not_called()


@pytest.mark.parametrize("mutated", [True, False])
def test_endpoint_group_listing_failure_reports_earlier_changes(mutated):
    def failing_query(module, client, method_name, result_key, error_msg, changed=False, **kwargs):
        module.fail_json(changed=changed, msg=error_msg)

    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", side_effect=failing_query),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_endpoint_groups(Mock(), FakeModule({}), "arn:listener", [], mutated=mutated)

    assert raised.value.values["changed"] is mutated


def tag_limit_case(check_mode, current_tags, tags):
    module = FakeModule(
        {
            "enabled": False,
            "ip_address_type": "IPV4",
            "ip_addresses": None,
            "listeners": [],
            "name": "renamed",
            "purge_tags": False,
            "tags": tags,
            "wait": False,
        },
        check_mode=check_mode,
    )
    current = {
        "AcceleratorArn": "arn:accelerator",
        "Enabled": True,
        "IpAddressType": "IPV4",
        "Name": "example",
        "Status": "DEPLOYED",
    }
    client = Mock()
    client.list_tags_for_resource.return_value = {
        "Tags": [{"Key": key, "Value": value} for key, value in current_tags.items()]
    }
    return module, current, client


@pytest.mark.parametrize("check_mode", [False, True])
def test_tag_limit_without_purge_fails_before_any_write(check_mode):
    module, current, client = tag_limit_case(
        check_mode,
        {f"existing{index}": "value" for index in range(40)},
        {f"new{index}": "value" for index in range(15)},
    )
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_accelerator") as waiter,
        patch.object(plugin, "ensure_listeners") as listeners,
        patch.object(plugin, "reconcile_arn_tags") as tagger,
        pytest.raises(ModuleFail) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["msg"] == "The resulting accelerator tags must contain at most 50 entries"
    waiter.assert_not_called()
    listeners.assert_not_called()
    tagger.assert_not_called()
    client.create_accelerator.assert_not_called()
    client.update_accelerator.assert_not_called()
    client.tag_resource.assert_not_called()
    client.untag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("current_tags", "new_tag_count"),
    [
        ({f"existing{index}": "value" for index in range(35)}, 15),
        (
            {
                **{f"existing{index}": "value" for index in range(40)},
                **{f"AWS:reserved{index}": "value" for index in range(10)},
            },
            10,
        ),
    ],
    ids=["under-limit", "aws-tags-excluded"],
)
def test_tag_limit_allows_up_to_fifty_user_tags(check_mode, current_tags, new_tag_count):
    tags = {f"new{index}": "value" for index in range(new_tag_count)}
    module, current, client = tag_limit_case(check_mode, current_tags, tags)
    client.update_accelerator.return_value = {"Accelerator": {**current, "Enabled": False, "Name": "renamed"}}
    with (
        patch.object(plugin, "get_accelerator", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_listener_writes"),
        patch.object(plugin, "require_endpoint_group_writes"),
        patch.object(plugin, "ensure_listeners", return_value=(False, [])),
        patch.object(plugin, "reconcile_arn_tags") as tagger,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is True
    assert result.value.values["accelerator"]["tags"] == {**current_tags, **tags}
    if check_mode:
        tagger.assert_not_called()
        client.update_accelerator.assert_not_called()
    else:
        tagger.assert_called_once()
        client.update_accelerator.assert_called_once()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "tags", [{"Team": "R&D"}, {"Team": "a,b"}, {"Team#1": "x"}], ids=["ampersand", "comma", "hash-key"]
)
def test_tag_characters_aws_rejects_fail_before_any_aws_call(check_mode, tags):
    # Live: TagResource rejects these with InvalidArgumentException, which an update reaches only after its accelerator,
    # listener, and endpoint group writes and the removal of purged tags.
    module = FakeModule(dict(present_params(None), tags=tags), check_mode=check_mode)
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client") as client_factory,
        patch.object(plugin, "ensure_present") as ensure_present,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": "tag keys and values must contain only letters, numbers, spaces, and _ . : / = + - @"
    }
    client_factory.assert_not_called()
    ensure_present.assert_not_called()


def test_tags_with_characters_aws_accepts_reach_aws():
    # Live: TagResource accepts these.
    module = FakeModule(dict(present_params(None), tags={"Team": "a b_.:/=+-@é1", "日本": "٣²"}))
    with (
        patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module),
        patch.object(module, "client"),
        patch.object(plugin, "ensure_present") as ensure_present,
    ):
        plugin.main()

    ensure_present.assert_called_once()


def run_recheck_and_update_waits(monotonic, waiter_results):
    """Run ensure_present for a deploying accelerator that must then be enabled and deployed again."""
    client = Mock()
    client.update_accelerator.return_value = {"Accelerator": deployed_accelerator(Status="IN_PROGRESS")}
    waiter = Mock()
    waiter.wait.side_effect = waiter_results
    module = FakeModule(accelerator_params(enabled=True, wait=True, wait_timeout=600))
    with (
        patch.object(
            plugin,
            "get_accelerator",
            side_effect=[
                deployed_accelerator(Enabled=False, Status="IN_PROGRESS"),
                deployed_accelerator(Enabled=False),
            ],
        ),
        patch.object(plugin, "get_accelerator_by_arn", return_value=deployed_accelerator()),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "custom_waiter", return_value=waiter),
        patch.object(wait_utils.time, "monotonic", side_effect=monotonic),
        pytest.raises(utils.ModuleResult) as raised,
    ):
        plugin.ensure_present(client, module)

    return raised.value, waiter


def test_sequential_waits_share_one_wait_timeout_budget():
    # The wait before the accelerator is checked again and the final deployment wait share 600s.
    result, waiter = run_recheck_and_update_waits([100, 100, 400], [None, None])

    assert isinstance(result, ModuleExit)
    assert [wait_call.kwargs["WaiterConfig"] for wait_call in waiter.wait.call_args_list] == [
        wait_utils.custom_waiter_config(timeout, default_pause=10) for timeout in (600, 300)
    ]


def test_an_exhausted_wait_timeout_budget_fails_with_the_timeout_message():
    result, waiter = run_recheck_and_update_waits([100, 100, 701], [None])

    waiter.wait.assert_called_once()
    assert isinstance(result, ModuleFail)
    assert result.values == {"changed": True, "msg": "Timed out waiting for AWS Global Accelerator arn:accelerator"}
