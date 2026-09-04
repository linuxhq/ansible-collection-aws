from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import notifications_hub as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class NotificationsHubTests(TestCase):
    def test_absent_tolerates_hub_disappearing_during_delete(self):
        client = Mock()
        client.deregister_notification_hub.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DeregisterNotificationHub",
        )
        module = FakeModule({"region": "us-east-1"})
        with (
            patch.object(plugin, "get_notification_hub", return_value={}),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])
        require.assert_called_once_with(
            module,
            client,
            "Notifications",
            {"deregister_notification_hub": ("notificationHubRegion",)},
        )

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["region"]["required"] is True

    def test_invalid_region_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {"region": "not-a-region", "state": "present"},
            "region must be a valid AWS region name",
        )

    def test_hub_lookup_matches_exact_region(self):
        hubs = [
            {"notificationHubRegion": "us-west-2", "statusSummary": {"reason": "", "status": "ACTIVE"}},
            {"notificationHubRegion": "us-east-1", "statusSummary": {"reason": "", "status": "ACTIVE"}},
        ]
        module = FakeModule({"region": "us-east-1"})
        with patch.object(plugin, "query_list", return_value=hubs):
            result = plugin.get_notification_hub(None, module)
        self.assertEqual(
            result,
            {"notificationHubRegion": "us-east-1", "statusSummary": {"reason": "", "status": "ACTIVE"}},
        )

    def test_hub_lookup_rejects_invalid_status(self):
        module = FakeModule({"region": "us-east-1"})
        with (
            patch.object(
                plugin,
                "query_list",
                return_value=[{"notificationHubRegion": "us-east-1", "statusSummary": {}}],
            ),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.get_notification_hub(None, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list AWS Notifications hubs: AWS returned an invalid hub",
        )

    def test_register_rejects_hub_for_different_region(self):
        client = Mock(register_notification_hub=Mock(return_value={"notificationHubRegion": "us-west-2"}))
        module = FakeModule({"region": "us-east-1"})
        with (
            patch.object(plugin, "get_notification_hub", return_value=None),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to create AWS Notifications hub us-east-1: AWS returned a hub for a different region",
        )

    def test_inactive_hub_is_registered_again(self):
        client = Mock(register_notification_hub=Mock(return_value={"notificationHubRegion": "us-east-1"}))
        module = FakeModule({"region": "us-east-1"})
        inactive = {
            "notificationHubRegion": "us-east-1",
            "statusSummary": {"status": "INACTIVE"},
        }
        with (
            patch.object(plugin, "get_notification_hub", return_value=inactive),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertTrue(raised.exception.values["changed"])
        client.register_notification_hub.assert_called_once_with(notificationHubRegion="us-east-1", aws_retry=True)
        require.assert_called_once_with(
            module,
            client,
            "Notifications",
            {"register_notification_hub": ("notificationHubRegion",)},
        )

    def test_inactive_hub_is_already_absent(self):
        client = Mock()
        module = FakeModule({"region": "us-east-1"})
        inactive = {
            "notificationHubRegion": "us-east-1",
            "statusSummary": {"status": "INACTIVE"},
        }
        with (
            patch.object(plugin, "get_notification_hub", return_value=inactive),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertFalse(raised.exception.values["changed"])
        client.deregister_notification_hub.assert_not_called()
        require.assert_not_called()

    def test_active_hub_does_not_require_register(self):
        client = Mock()
        module = FakeModule({"region": "us-east-1"})
        active = {
            "notificationHubRegion": "us-east-1",
            "statusSummary": {"status": "ACTIVE"},
        }
        with (
            patch.object(plugin, "get_notification_hub", return_value=active),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertFalse(raised.exception.values["changed"])
        client.register_notification_hub.assert_not_called()
        require.assert_not_called()
