from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import notifications_hub_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class NotificationsHubInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"] == {}

    def test_returns_normalized_hubs(self):
        module = FakeModule({}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "query_list",
                return_value=[
                    {
                        "creationTime": "2026-01-01T00:00:00Z",
                        "notificationHubRegion": "us-east-1",
                        "statusSummary": {"reason": "", "status": "ACTIVE"},
                    }
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["notification_hubs"],
            [
                {
                    "creation_time": "2026-01-01T00:00:00Z",
                    "notification_hub_region": "us-east-1",
                    "status_summary": {"reason": "", "status": "ACTIVE"},
                }
            ],
        )
        require.assert_called_once_with(
            module,
            module.client(),
            "Notifications",
            {"list_notification_hubs": ("maxResults", "nextToken")},
        )

    def test_rejects_invalid_hub(self):
        module = FakeModule({}, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[{"notificationHubRegion": "us-east-1"}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list AWS Notifications hubs: AWS returned an invalid hub",
        )
