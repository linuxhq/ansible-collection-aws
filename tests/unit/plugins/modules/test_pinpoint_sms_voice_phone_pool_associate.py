from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_pool_associate as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class PinpointSmsVoicePhonePoolAssociateTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["pool_id"]["required"] is True
        assert "required" not in options["argument_spec"]["iso_country_code"]

    def test_list_capability_includes_pagination_parameters(self):
        module = FakeModule(
            {
                "client_token": None,
                "iso_country_code": None,
                "origination_identity": "sender-1",
                "pool_id": "pool-1",
                "state": "present",
            },
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "ensure_present"),
        ):
            plugin.main()

        self.assertEqual(
            require.call_args.args[3]["list_pool_origination_identities"],
            ("PoolId", "MaxResults", "NextToken"),
        )

    def test_association_matches_id_or_arn(self):
        module = SimpleNamespace(params={"iso_country_code": "US", "origination_identity": "arn:phone"})
        associations = [
            {
                "IsoCountryCode": "US",
                "OriginationIdentity": "phone-1",
                "OriginationIdentityArn": "arn:phone",
            }
        ]
        assert plugin.current_association(module, associations) == associations[0]

    def test_association_request_omits_empty_client_token(self):
        module = SimpleNamespace(
            params={
                "client_token": None,
                "iso_country_code": "US",
                "origination_identity": "phone-1",
                "pool_id": "pool-1",
            }
        )
        assert plugin.association_request(module) == {
            "IsoCountryCode": "US",
            "OriginationIdentity": "phone-1",
            "PoolId": "pool-1",
        }

    def test_country_code_is_optional_for_non_country_specific_identities(self):
        module = SimpleNamespace(
            params={
                "client_token": None,
                "iso_country_code": None,
                "origination_identity": "sender-1",
                "pool_id": "pool-1",
            }
        )
        association = {
            "IsoCountryCode": "US",
            "OriginationIdentity": "sender-1",
        }
        assert plugin.current_association(module, [association]) == association
        assert plugin.association_request(module) == {
            "OriginationIdentity": "sender-1",
            "PoolId": "pool-1",
        }

    def test_absent_does_not_return_association_that_disappeared(self):
        client = Mock()
        client.disassociate_origination_identity.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DisassociateOriginationIdentity",
        )
        module = FakeModule(
            {
                "client_token": None,
                "iso_country_code": None,
                "origination_identity": "sender-1",
                "pool_id": "pool-1",
                "state": "absent",
            }
        )
        with (
            patch.object(
                plugin,
                "current_associations",
                return_value=[{"OriginationIdentity": "sender-1"}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertEqual(raised.exception.values["association"], {})

    def test_rejects_lowercase_country_code(self):
        module = FakeModule({"iso_country_code": "us", "state": "present"})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("uppercase", raised.exception.values["msg"])
