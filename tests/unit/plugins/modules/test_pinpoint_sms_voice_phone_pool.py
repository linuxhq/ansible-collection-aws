from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_pool as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class PinpointSmsVoicePhonePoolTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert len(options["required_if"]) == 2

    def test_optional_create_parameters_are_not_gated_when_omitted(self):
        client = Mock()
        module = FakeModule(
            {
                "client_token": None,
                "iso_country_code": None,
                "message_type": "TRANSACTIONAL",
                "name": "main",
                "origination_identity": "sender-1",
                "pool_id": None,
                "purge_tags": True,
                "state": "present",
                "tags": None,
                "wait": False,
                "wait_delay": 5,
                "wait_timeout": 300,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "ensure_present"),
        ):
            plugin.main()

        methods = require.call_args.args[3]
        self.assertEqual(
            methods["describe_pools"],
            ("Filters", "Owner", "MaxResults", "NextToken"),
        )
        self.assertEqual(
            methods["list_pool_origination_identities"],
            ("PoolId", "MaxResults", "NextToken"),
        )
        self.assertEqual(
            methods["create_pool"],
            (
                "DeletionProtectionEnabled",
                "MessageType",
                "OriginationIdentity",
                "Tags",
            ),
        )
        self.assertNotIn("tag_resource", methods)

    def test_rejects_lowercase_country_code(self):
        module = FakeModule({"iso_country_code": "us", "state": "present"})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("uppercase", raised.exception.values["msg"])

    def test_name_tag_counts_toward_provider_limit(self):
        module = FakeModule(
            {
                "iso_country_code": None,
                "name": "main",
                "state": "present",
                "tags": {str(index): "" for index in range(200)},
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["msg"], "tags must contain at most 200 entries")

    def test_existing_pool_rejects_message_type_change(self):
        module = FakeModule(
            {
                "deletion_protection_enabled": False,
                "message_type": "TRANSACTIONAL",
                "wait": False,
            }
        )
        with (
            patch.object(
                plugin,
                "find_pool",
                return_value={"MessageType": "PROMOTIONAL", "PoolId": "pool-1"},
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(Mock(), module)
        self.assertIn("Cannot modify message_type", raised.exception.values["msg"])

    def test_missing_explicit_pool_id_is_not_replaced_with_an_unselectable_pool(self):
        module = FakeModule(
            {
                "deletion_protection_enabled": False,
                "message_type": "TRANSACTIONAL",
                "pool_id": "pool-missing",
                "wait": False,
            }
        )
        with (
            patch.object(plugin, "find_pool", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertIn("does not exist", raised.exception.values["msg"])

    def test_pool_lookup_uses_name_tag_to_disambiguate_sender_pools(self):
        module = FakeModule(
            {
                "iso_country_code": None,
                "message_type": "TRANSACTIONAL",
                "name": "second",
                "origination_identity": "sender-1",
                "pool_id": None,
            }
        )
        pools = [
            {"PoolId": "pool-1", "Status": "ACTIVE"},
            {"PoolId": "pool-2", "Status": "ACTIVE"},
        ]

        with (
            patch.object(plugin, "describe_pools", return_value=pools),
            patch.object(
                plugin,
                "pool_with_origination_identities",
                side_effect=lambda client, module, pool: dict(
                    pool,
                    OriginationIdentities=[{"OriginationIdentity": "sender-1"}],
                ),
            ),
            patch.object(
                plugin,
                "pool_with_tags",
                side_effect=[
                    dict(pools[0], Tags=[{"Key": "Name", "Value": "first"}]),
                    dict(pools[1], Tags=[{"Key": "Name", "Value": "second"}]),
                ],
            ),
        ):
            result = plugin.find_pool(Mock(), module)

        self.assertEqual(result["PoolId"], "pool-2")

    def test_check_mode_projects_new_pool_identity_and_name_tag(self):
        client = Mock()
        module = FakeModule(
            {
                "deletion_protection_enabled": True,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "name": "primary",
                "origination_identity": "phone-1",
                "purge_tags": True,
                "state": "present",
                "tags": {"Environment": "test"},
                "wait": False,
            },
            check_mode=True,
        )
        with (
            patch.object(plugin, "find_pool", return_value=None),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        pool = raised.exception.values["pool"]
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            pool["origination_identities"],
            [{"iso_country_code": "US", "origination_identity": "phone-1"}],
        )
        self.assertEqual(pool["tags"], {"Environment": "test", "Name": "primary"})
        client.create_pool.assert_not_called()

    def test_check_mode_preserves_existing_empty_pool_identities(self):
        current = {
            "DeletionProtectionEnabled": False,
            "MessageType": "TRANSACTIONAL",
            "OriginationIdentities": [],
            "PoolArn": "arn:pool",
            "PoolId": "pool-1",
            "Status": "ACTIVE",
            "Tags": [{"Key": "Name", "Value": "primary"}],
        }
        module = FakeModule(
            {
                "deletion_protection_enabled": True,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "name": "primary",
                "origination_identity": "phone-1",
                "pool_id": "pool-1",
                "purge_tags": True,
                "state": "present",
                "tags": None,
                "wait": False,
            },
            check_mode=True,
        )
        with (
            patch.object(plugin, "find_pool", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertEqual(raised.exception.values["pool"]["origination_identities"], [])

    def test_no_wait_creation_uses_create_result_without_retagging(self):
        client = Mock()
        client.create_pool.return_value = {
            "PoolArn": "arn:pool",
            "PoolId": "pool-1",
            "Status": "CREATING",
        }
        module = FakeModule(
            {
                "client_token": None,
                "deletion_protection_enabled": False,
                "iso_country_code": "US",
                "message_type": "TRANSACTIONAL",
                "name": "primary",
                "origination_identity": "phone-1",
                "purge_tags": True,
                "state": "present",
                "tags": {"Environment": "test"},
                "wait": False,
            }
        )
        with (
            patch.object(plugin, "find_pool", return_value=None),
            patch.object(plugin, "get_pool_by_id") as get_pool_by_id,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["pool"]["tags"],
            {"Environment": "test", "Name": "primary"},
        )
        get_pool_by_id.assert_not_called()
        client.tag_resource.assert_not_called()

    def test_no_wait_update_waits_for_transition_and_rechecks_state(self):
        client = Mock()
        module = FakeModule(
            {
                "deletion_protection_enabled": True,
                "message_type": "TRANSACTIONAL",
                "name": "primary",
                "purge_tags": True,
                "state": "present",
                "tags": None,
                "wait": False,
            }
        )
        transitioning = {
            "DeletionProtectionEnabled": False,
            "MessageType": "TRANSACTIONAL",
            "PoolId": "pool-1",
            "Status": "UPDATING",
            "Tags": [{"Key": "Name", "Value": "primary"}],
        }
        active = dict(
            transitioning,
            DeletionProtectionEnabled=True,
            Status="ACTIVE",
        )
        with (
            patch.object(plugin, "find_pool", return_value=transitioning),
            patch.object(plugin, "wait_for_pool_active") as wait_for_pool_active,
            patch.object(plugin, "get_pool_by_id", return_value=active),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        wait_for_pool_active.assert_called_once_with(client, module, "pool-1")
        client.update_pool.assert_not_called()
        self.assertFalse(raised.exception.values["changed"])

    def test_deleting_pool_stops_activation_wait(self):
        module = FakeModule({"wait_delay": 1, "wait_timeout": 10})
        with (
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(
                plugin,
                "describe_pools",
                return_value=[{"PoolId": "pool-1", "Status": "DELETING"}],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.wait_for_pool_active(Mock(), module, "pool-1")
        self.assertEqual(raised.exception.values["status"], "DELETING")

    def test_absent_activation_wait_accepts_external_deletion(self):
        module = FakeModule({"state": "absent", "wait_delay": 1, "wait_timeout": 10})
        deleting = {"PoolId": "pool-1", "Status": "DELETING"}
        with (
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(plugin, "describe_pools", return_value=[deleting]),
        ):
            result = plugin.wait_for_pool_active(Mock(), module, "pool-1")

        self.assertEqual(result, deleting)

    def test_absent_stops_when_wait_observes_external_deletion(self):
        client = Mock()
        module = FakeModule({"pool_id": "pool-1", "state": "absent"})
        with (
            patch.object(
                plugin,
                "describe_pools",
                return_value=[{"PoolId": "pool-1", "Status": "UPDATING"}],
            ),
            patch.object(
                plugin,
                "wait_for_pool_active",
                return_value={"PoolId": "pool-1", "Status": "DELETING"},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertTrue(raised.exception.values["changed"])
        client.delete_pool.assert_not_called()

    def test_absent_tolerates_disappearing_deletion_protection_update(self):
        client = Mock()
        client.update_pool.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "UpdatePool",
        )
        module = FakeModule({"pool_id": "pool-1", "state": "absent"})
        with (
            patch.object(
                plugin,
                "describe_pools",
                return_value=[
                    {
                        "DeletionProtectionEnabled": True,
                        "PoolId": "pool-1",
                        "Status": "ACTIVE",
                    }
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertTrue(raised.exception.values["changed"])
        client.delete_pool.assert_not_called()

    def test_absent_disables_deletion_protection_before_deleting(self):
        client = Mock()
        client.update_pool.return_value = {
            "DeletionProtectionEnabled": False,
            "PoolId": "pool-1",
            "Status": "UPDATING",
        }
        client.delete_pool.return_value = {"PoolId": "pool-1", "Status": "DELETING"}
        module = FakeModule({"pool_id": "pool-1", "state": "absent"})

        with (
            patch.object(
                plugin,
                "describe_pools",
                return_value=[
                    {
                        "DeletionProtectionEnabled": True,
                        "PoolId": "pool-1",
                        "Status": "ACTIVE",
                    }
                ],
            ),
            patch.object(plugin, "wait_for_pool_active") as wait_for_pool_active,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        client.update_pool.assert_called_once_with(
            PoolId="pool-1",
            DeletionProtectionEnabled=False,
            aws_retry=True,
        )
        wait_for_pool_active.assert_called_once_with(client, module, "pool-1")
        client.delete_pool.assert_called_once_with(PoolId="pool-1", aws_retry=True)
        self.assertTrue(raised.exception.values["changed"])
