from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    notifications_contacts_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class NotificationsContactsInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["arn"]["type"] == "str"

    def test_arn_uses_get_and_loads_tags(self):
        client = Mock(
            get_email_contact=Mock(
                return_value={
                    "emailContact": {"arn": "arn:contact", "address": "a@example.com"}
                }
            ),
            list_tags_for_resource=Mock(return_value={"tags": {"Env": "test"}}),
        )
        module = FakeModule({"arn": "arn:contact"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["email_contacts"][0]["tags"], {"Env": "test"}
        )
        self.assertEqual(
            [call.args[3] for call in require.call_args_list],
            [
                {"get_email_contact": ("arn",)},
                {"list_tags_for_resource": ("arn",)},
            ],
        )

    def test_list_requires_pagination_parameters(self):
        client = Mock(list_email_contacts=Mock(return_value={"emailContacts": []}))
        module = FakeModule({"arn": None}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "query_list", return_value=[]),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        require.assert_called_once_with(
            module,
            client,
            "NotificationsContacts",
            {"list_email_contacts": ("maxResults", "nextToken")},
        )
