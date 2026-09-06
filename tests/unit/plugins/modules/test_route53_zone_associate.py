from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import route53_zone_associate as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class Route53ZoneAssociateTests(TestCase):
    def test_absent_tolerates_association_disappearing_during_delete(self):
        client = Mock()
        client.disassociate_vpc_from_hosted_zone.side_effect = plugin.ClientError(
            {"Error": {"Code": "VPCAssociationNotFound", "Message": "gone"}},
            "DisassociateVPCFromHostedZone",
        )
        module = FakeModule({"vpc_id": "vpc-1", "vpc_region": "us-east-1"})
        with (
            patch.object(
                plugin,
                "get_vpc_associations",
                return_value=[{"VPCId": "vpc-1", "VPCRegion": "us-east-1"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module, "zone-1")

        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert all(options["argument_spec"][key]["required"] for key in ("hosted_zone_id", "vpc_id", "vpc_region"))

    def test_invalid_vpc_region_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "hosted_zone_id": "Z1",
                "state": "present",
                "vpc_id": "vpc-1",
                "vpc_region": "invalid",
            },
            "vpc_region must be a valid AWS region name",
        )

    def test_vpc_associations_are_normalized_and_sorted(self):
        module = SimpleNamespace(params={"vpc_id": "vpc-2", "vpc_region": "us-west-2"})
        assert plugin.route53_vpc(module) == {
            "VPCId": "vpc-2",
            "VPCRegion": "us-west-2",
        }
        assert plugin.route53_vpc_list(
            [
                {"VPCId": "vpc-2", "VPCRegion": "us-west-2", "Ignored": True},
                {"VPCId": "vpc-1", "VPCRegion": "us-east-1"},
            ]
        ) == [
            {"VPCId": "vpc-1", "VPCRegion": "us-east-1"},
            {"VPCId": "vpc-2", "VPCRegion": "us-west-2"},
        ]

    def test_get_vpc_associations_rejects_invalid_response(self):
        client = Mock()
        client.get_hosted_zone.return_value = {"VPCs": {}}
        module = FakeModule({})

        with self.assertRaises(ModuleFail) as raised:
            plugin.get_vpc_associations(client, module, "Z1")

        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Route53 returned an invalid hosted zone response for Z1",
        )

    def test_get_vpc_associations_rejects_invalid_vpc(self):
        client = Mock()
        client.get_hosted_zone.return_value = {"VPCs": [{"VPCId": "vpc-1"}]}
        module = FakeModule({})

        with self.assertRaises(ModuleFail) as raised:
            plugin.get_vpc_associations(client, module, "Z1")

        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Route53 returned an invalid VPC association for hosted zone Z1",
        )

    def test_check_mode_projects_the_new_association(self):
        client = Mock()
        module = FakeModule({"vpc_id": "vpc-2", "vpc_region": "us-west-2"}, check_mode=True)
        with (
            patch.object(
                plugin,
                "get_vpc_associations",
                return_value=[{"VPCId": "vpc-1", "VPCRegion": "us-east-1"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module, "Z1")

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            [vpc["vpc_id"] for vpc in raised.exception.values["vpcs"]],
            ["vpc-1", "vpc-2"],
        )
        client.associate_vpc_with_hosted_zone.assert_not_called()
