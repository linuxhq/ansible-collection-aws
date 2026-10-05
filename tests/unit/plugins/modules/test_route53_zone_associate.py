from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from botocore.session import Session

from ansible_collections.linuxhq.aws.plugins.modules import route53_zone_associate as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

VPC_1 = {"VPCId": "vpc-1", "VPCRegion": "us-east-1"}
VPC_2 = {"VPCId": "vpc-2", "VPCRegion": "us-west-2"}


def params(**overrides):
    values = {
        "hosted_zone_id": "Z1",
        "state": "present",
        "vpc_id": "vpc-1",
        "vpc_region": "us-east-1",
        "wait": False,
        "wait_delay": 5,
        "wait_timeout": 300,
    }
    values.update(overrides)
    return values


def zone(vpcs, found=True, private=True, shared=False):
    return {"found": found, "private": private, "shared": shared, "vpcs": vpcs}


def client_error(code, operation):
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


def run_main(module):
    with patch.object(plugin, "AnsibleAWSModule", return_value=module), pytest.raises(ModuleFail) as raised:
        plugin.main()

    return raised.value.values["msg"]


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    spec = captured["argument_spec"]
    assert captured["supports_check_mode"]
    assert all(spec[key]["required"] for key in ("hosted_zone_id", "vpc_id", "vpc_region"))
    assert spec["wait"]["default"] is False
    assert spec["wait_timeout"]["default"] == 300
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_invalid_vpc_region_is_rejected():
    assert run_main(FakeModule(params(vpc_region="invalid"))) == "vpc_region must be a valid AWS region name"


def test_every_modeled_vpc_region_is_accepted():
    regions = Session().get_service_model("route53").shape_for("VPCRegion").enum
    for region in regions:
        module = FakeModule(params(vpc_region=region), client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "ensure_present", side_effect=ModuleExit({})),
            pytest.raises(ModuleExit),
        ):
            plugin.main()


def test_wait_bounds_are_validated_when_waiting():
    assert run_main(FakeModule(params(wait=True, wait_delay=0))) == "wait_delay must be 1 or greater"


def test_client_retries_prior_request_not_complete():
    module = FakeModule(params())
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin.AWSRetry, "jittered_backoff") as jittered_backoff,
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    jittered_backoff.assert_called_once_with(catch_extra_error_codes=["PriorRequestNotComplete"])


def test_vpc_associations_are_normalized_and_sorted():
    module = SimpleNamespace(params={"vpc_id": "vpc-2", "vpc_region": "us-west-2"})
    assert plugin.route53_vpc(module) == VPC_2
    assert plugin.route53_vpc_list([dict(VPC_2, Ignored=True), VPC_1]) == [VPC_1, VPC_2]


def test_get_hosted_zone_reports_privacy_and_vpcs():
    client = Mock()
    client.get_hosted_zone.return_value = {"HostedZone": {"Config": {"PrivateZone": True}}, "VPCs": [VPC_1]}
    assert plugin.get_hosted_zone(client, FakeModule(params()), "Z1") == zone([VPC_1])

    client.get_hosted_zone.return_value = {"HostedZone": {"Config": {"PrivateZone": False}}}
    assert plugin.get_hosted_zone(client, FakeModule(params()), "Z1") == zone([], private=False)


def test_get_hosted_zone_reports_missing_zone():
    client = Mock()
    client.get_hosted_zone.side_effect = client_error("NoSuchHostedZone", "GetHostedZone")
    assert plugin.get_hosted_zone(client, FakeModule(params()), "Z1") == zone([], found=False, private=False)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({"VPCs": {}}, "AWS Route53 returned an invalid hosted zone response for Z1"),
        ({"VPCs": [{"VPCId": "vpc-1"}]}, "AWS Route53 returned an invalid VPC association for hosted zone Z1"),
    ],
)
def test_get_hosted_zone_rejects_invalid_response(response, message):
    client = Mock()
    client.get_hosted_zone.return_value = response
    with pytest.raises(ModuleFail) as raised:
        plugin.get_hosted_zone(client, FakeModule(params()), "Z1")

    assert raised.value.values["msg"] == message


@pytest.mark.parametrize(("listed", "expected"), [("/hostedzone/Z1", [VPC_1]), ("Z2", [])])
def test_zone_owned_by_another_account_is_looked_up_by_vpc(listed, expected):
    client = Mock()
    client.get_hosted_zone.side_effect = client_error("AccessDenied", "GetHostedZone")
    with (
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=[{"HostedZoneId": listed}]) as query_list,
    ):
        result = plugin.get_hosted_zone(client, FakeModule(params()), "Z1")

    assert result == zone(expected, shared=True)
    assert "list_hosted_zones_by_vpc" in require_client_methods.call_args.args[3]
    assert query_list.call_args.kwargs == {"VPCId": "vpc-1", "VPCRegion": "us-east-1"}


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("current", "message"),
    [
        (zone([], found=False, private=False), "AWS Route53 hosted zone Z1 does not exist"),
        (
            zone([], private=False),
            "AWS Route53 hosted zone Z1 is public; VPCs can be associated only with private hosted zones",
        ),
    ],
)
def test_present_fails_for_missing_or_public_zone(check_mode, current, message):
    client = Mock()
    with (
        patch.object(plugin, "get_hosted_zone", return_value=current),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(), check_mode=check_mode), "Z1")

    assert raised.value.values["msg"] == message
    client.associate_vpc_with_hosted_zone.assert_not_called()


def test_absent_reports_no_change_for_missing_zone():
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([], found=False, private=False)),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(Mock(), FakeModule(params(state="absent")), "Z1")

    assert not raised.value.values["changed"]


@pytest.mark.parametrize("check_mode", [False, True])
def test_absent_fails_before_removing_the_last_vpc(check_mode):
    client = Mock()
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([VPC_1])),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, FakeModule(params(state="absent"), check_mode=check_mode), "Z1")

    assert "because it is the last VPC associated with the private hosted zone" in raised.value.values["msg"]
    client.disassociate_vpc_from_hosted_zone.assert_not_called()


def test_absent_explains_last_vpc_rejection_for_shared_zone():
    client = Mock()
    client.disassociate_vpc_from_hosted_zone.side_effect = client_error(
        "LastVPCAssociation", "DisassociateVPCFromHostedZone"
    )
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([VPC_1], shared=True)),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, FakeModule(params(state="absent")), "Z1")

    assert "because it is the last VPC associated with the private hosted zone" in raised.value.values["msg"]


def test_absent_tolerates_association_disappearing_during_delete():
    client = Mock()
    client.disassociate_vpc_from_hosted_zone.side_effect = client_error(
        "VPCAssociationNotFound", "DisassociateVPCFromHostedZone"
    )
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([VPC_1, VPC_2])),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, FakeModule(params(state="absent", wait=True)), "Z1")

    assert raised.value.values["changed"]
    assert raised.value.values["vpcs"] == [{"vpc_id": "vpc-2", "vpc_region": "us-west-2"}]
    client.get_waiter.assert_not_called()


def test_check_mode_projects_the_new_association():
    client = Mock()
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([VPC_1])),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(vpc_id="vpc-2", vpc_region="us-west-2"), check_mode=True), "Z1")

    assert raised.value.values["changed"]
    assert [vpc["vpc_id"] for vpc in raised.value.values["vpcs"]] == ["vpc-1", "vpc-2"]
    client.associate_vpc_with_hosted_zone.assert_not_called()


@pytest.mark.parametrize("state", ["absent", "present"])
def test_wait_polls_the_returned_change(state):
    client = Mock()
    response = {"ChangeInfo": {"Id": "/change/C1", "Status": "PENDING"}}
    client.associate_vpc_with_hosted_zone.return_value = response
    client.disassociate_vpc_from_hosted_zone.return_value = response
    current = [VPC_1, VPC_2] if state == "absent" else [VPC_2]
    ensure = plugin.ensure_absent if state == "absent" else plugin.ensure_present
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone(current)),
        pytest.raises(ModuleExit) as raised,
    ):
        ensure(client, FakeModule(params(state=state, wait=True, wait_delay=7, wait_timeout=70)), "Z1")

    assert raised.value.values["changed"]
    client.get_waiter.assert_called_once_with("resource_record_sets_changed")
    client.get_waiter.return_value.wait.assert_called_once_with(
        Id="/change/C1", WaiterConfig=plugin.custom_waiter_config(70, default_pause=7)
    )


def test_no_wait_by_default():
    client = Mock()
    client.associate_vpc_with_hosted_zone.return_value = {"ChangeInfo": {"Id": "/change/C1"}}
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([VPC_2])),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, FakeModule(params()), "Z1")

    client.get_waiter.assert_not_called()


@pytest.mark.parametrize("state", ["absent", "present"])
def test_wait_failure_after_a_change_reports_changed(state):
    client = Mock()
    response = {"ChangeInfo": {"Id": "/change/C1"}}
    client.associate_vpc_with_hosted_zone.return_value = response
    client.disassociate_vpc_from_hosted_zone.return_value = response
    client.get_waiter.return_value.wait.side_effect = client_error("Throttling", "GetChange")
    ensure = plugin.ensure_absent if state == "absent" else plugin.ensure_present
    vpcs = [VPC_1, VPC_2] if state == "absent" else [VPC_2]
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone(vpcs)),
        pytest.raises(ModuleFail) as raised,
    ):
        ensure(client, FakeModule(params(state=state, wait=True)), "Z1")

    assert raised.value.values["changed"] is True


def test_missing_change_id_after_a_change_reports_changed():
    client = Mock(associate_vpc_with_hosted_zone=Mock(return_value={}))
    with (
        patch.object(plugin, "get_hosted_zone", return_value=zone([VPC_2])),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params(wait=True)), "Z1")

    assert raised.value.values["changed"] is True
