from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_number as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class PinpointSmsVoicePhoneNumberTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert len(options["required_if"]) == 2

    def test_accepts_four_capabilities(self):
        client = Mock()
        module = FakeModule(
            {
                "client_token": None,
                "deletion_protection_enabled": False,
                "international_sending_enabled": None,
                "number_capabilities": ["MMS", "RCS", "SMS", "VOICE"],
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "number_type": "LONG_CODE",
                "opt_out_list_name": None,
                "pool_id": None,
                "registration_id": None,
                "state": "present",
                "tags": None,
                "wait": False,
                "wait_delay": 5,
                "wait_timeout": 300,
            },
            check_mode=True,
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require.assert_called_once_with(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {
                "describe_phone_numbers": (
                    "MaxResults",
                    "NextToken",
                    "Filters",
                    "Owner",
                )
            },
        )
        client.request_phone_number.assert_not_called()

    def test_capability_limit_counts_unique_values(self):
        client = Mock()
        module = FakeModule(
            {
                "client_token": None,
                "deletion_protection_enabled": False,
                "international_sending_enabled": None,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "number_capabilities": ["SMS"] * 5,
                "number_type": "LONG_CODE",
                "opt_out_list_name": None,
                "pool_id": None,
                "registration_id": None,
                "state": "present",
                "tags": None,
                "wait": False,
                "wait_delay": 5,
                "wait_timeout": 300,
            },
            check_mode=True,
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

    def test_simulator_numbers_require_transactional_messages(self):
        module = FakeModule(
            {
                "iso_country_code": "US",
                "message_type": "PROMOTIONAL",
                "number_capabilities": ["SMS"],
                "number_type": "SIMULATOR",
                "state": "present",
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("must be TRANSACTIONAL", raised.exception.values["msg"])

    def test_existing_number_matches_capabilities_without_order(self):
        client = Mock()
        module = FakeModule(
            {
                "deletion_protection_enabled": False,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "number_capabilities": ["SMS", "VOICE"],
                "number_type": "LONG_CODE",
                "opt_out_list_name": None,
                "pool_id": None,
                "registration_id": None,
                "state": "present",
                "tags": None,
                "wait": False,
            }
        )
        current = {
            "DeletionProtectionEnabled": False,
            "IsoCountryCode": "US",
            "MessageType": "TRANSACTIONAL",
            "NumberCapabilities": ["VOICE", "SMS"],
            "NumberType": "LONG_CODE",
            "PhoneNumberId": "phone-1",
            "Status": "ACTIVE",
        }
        with (
            patch.object(plugin, "query_list", return_value=[current]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertFalse(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["phone_number_id"], "phone-1")
        client.request_phone_number.assert_not_called()

    def test_existing_number_matches_pool_and_opt_out_list_arns(self):
        client = Mock()
        module = FakeModule(
            {
                "deletion_protection_enabled": False,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "number_capabilities": ["SMS"],
                "number_type": "LONG_CODE",
                "opt_out_list_name": "arn:aws:sms-voice:us-east-1:1:opt-out-list/list-1",
                "pool_id": "arn:aws:sms-voice:us-east-1:1:pool/pool-1",
                "registration_id": None,
                "state": "present",
                "tags": None,
                "wait": False,
            }
        )
        current = {
            "DeletionProtectionEnabled": False,
            "IsoCountryCode": "US",
            "MessageType": "TRANSACTIONAL",
            "NumberCapabilities": ["SMS"],
            "NumberType": "LONG_CODE",
            "OptOutListName": "list-1",
            "PhoneNumberId": "phone-1",
            "PoolId": "pool-1",
            "Status": "ACTIVE",
        }
        with (
            patch.object(plugin, "query_list", return_value=[current]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertFalse(raised.exception.values["changed"])
        client.request_phone_number.assert_not_called()

    def test_check_mode_projects_deduplicated_request_without_client_token(self):
        client = Mock()
        module = FakeModule(
            {
                "client_token": "secret-token",
                "deletion_protection_enabled": True,
                "international_sending_enabled": False,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "number_capabilities": ["VOICE", "SMS", "SMS"],
                "number_type": "LONG_CODE",
                "opt_out_list_name": None,
                "pool_id": None,
                "registration_id": None,
                "state": "present",
                "tags": None,
                "wait": False,
            },
            check_mode=True,
        )
        with (
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        phone_number = raised.exception.values["phone_number"]
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(phone_number["number_capabilities"], ["SMS", "VOICE"])
        self.assertNotIn("client_token", phone_number)
        client.request_phone_number.assert_not_called()

    def test_deleted_number_stops_activation_wait(self):
        module = FakeModule(
            {
                "tags": None,
                "wait_delay": 1,
                "wait_timeout": 10,
            }
        )
        with (
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(
                plugin,
                "get_phone_number",
                return_value={"PhoneNumberId": "phone-1", "Status": "DELETED"},
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.wait_for_phone_number_active(Mock(), module, "phone-1")
        self.assertEqual(raised.exception.values["status"], "DELETED")

    def test_absent_activation_wait_does_not_fetch_tags(self):
        client = Mock()
        module = FakeModule(
            {
                "state": "absent",
                "tags": {"Name": "ignored"},
                "wait_delay": 1,
                "wait_timeout": 10,
            }
        )
        with (
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(
                plugin,
                "get_phone_number",
                return_value={
                    "PhoneNumberArn": "arn:phone-1",
                    "PhoneNumberId": "phone-1",
                    "Status": "ACTIVE",
                },
            ),
        ):
            plugin.wait_for_phone_number_active(client, module, "phone-1")

        client.list_tags_for_resource.assert_not_called()

    def test_absent_activation_wait_accepts_external_deletion(self):
        module = FakeModule(
            {
                "state": "absent",
                "tags": None,
                "wait_delay": 1,
                "wait_timeout": 10,
            }
        )
        deleted = {"PhoneNumberId": "phone-1", "Status": "DELETED"}
        with (
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(plugin, "get_phone_number", return_value=deleted),
        ):
            result = plugin.wait_for_phone_number_active(Mock(), module, "phone-1")

        self.assertEqual(result, deleted)

    def test_absent_removes_pool_and_deletion_protection_before_release(self):
        client = Mock()
        client.update_phone_number.return_value = {
            "DeletionProtectionEnabled": False,
            "PhoneNumberId": "phone-1",
            "Status": "UPDATING",
        }
        client.release_phone_number.return_value = {
            "PhoneNumberId": "phone-1",
            "Status": "DELETED",
        }
        module = FakeModule({"phone_number_id": "phone-1", "state": "absent", "tags": None})

        with (
            patch.object(
                plugin,
                "get_phone_number",
                return_value={
                    "DeletionProtectionEnabled": True,
                    "PhoneNumberId": "phone-1",
                    "PoolId": "pool-1",
                    "Status": "ACTIVE",
                },
            ),
            patch.object(plugin, "wait_for_phone_number_active") as wait_for_phone_number_active,
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        client.disassociate_origination_identity.assert_called_once_with(
            PoolId="pool-1",
            OriginationIdentity="phone-1",
            aws_retry=True,
        )
        client.update_phone_number.assert_called_once_with(
            PhoneNumberId="phone-1",
            DeletionProtectionEnabled=False,
            aws_retry=True,
        )
        wait_for_phone_number_active.assert_called_once_with(client, module, "phone-1")
        client.release_phone_number.assert_called_once_with(PhoneNumberId="phone-1", aws_retry=True)
        self.assertTrue(raised.exception.values["changed"])

    def test_absent_tolerates_disappearing_prerequisites(self):
        missing = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DeletePhoneNumber",
        )
        client = Mock()
        client.disassociate_origination_identity.side_effect = missing
        client.update_phone_number.side_effect = missing
        module = FakeModule({"phone_number_id": "phone-1", "state": "absent"})

        with (
            patch.object(
                plugin,
                "get_phone_number",
                return_value={
                    "DeletionProtectionEnabled": True,
                    "PhoneNumberId": "phone-1",
                    "PoolId": "pool-1",
                    "Status": "ACTIVE",
                },
            ),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertTrue(raised.exception.values["changed"])
        client.release_phone_number.assert_not_called()
