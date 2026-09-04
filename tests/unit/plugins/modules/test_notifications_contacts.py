from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import notifications_contacts as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class NotificationsContactsTests(TestCase):
    def test_absent_tolerates_contact_disappearing_during_delete(self):
        client = Mock()
        client.delete_email_contact.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DeleteEmailContact",
        )
        module = FakeModule({"email_address": "ops@example.com"})
        with (
            patch.object(
                plugin,
                "get_contact_by_address",
                return_value={"arn": "arn:contact"},
            ),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_if"] == [("state", "present", ["name"])]
        assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]

    def test_list_rejects_invalid_contacts(self):
        client = Mock()
        module = FakeModule({"email_address": "ops@example.com"})
        with (
            patch.object(plugin, "query_list", return_value=[{"address": "ops@example.com"}]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.get_contact_by_address(client, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list AWS Notifications contacts: AWS returned an invalid contact",
        )

    def test_tag_deltas_remove_and_replace_tags(self):
        contact = {"arn": "arn:contact", "tags": {"keep": "old", "remove": "yes"}}
        assert plugin.apply_tag_deltas(contact, {"keep": "new"}, ["remove"]) == {
            "arn": "arn:contact",
            "tags": {"keep": "new"},
        }
        assert contact["tags"]["keep"] == "old"

    def test_tag_only_update_does_not_recreate_the_contact(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {"tags": {"keep": "old", "remove": "yes"}}
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": {"keep": "new"},
            }
        )
        contact = {
            "address": "ops@example.com",
            "arn": "arn:contact",
            "name": "Operations",
        }
        with (
            patch.object(plugin, "get_contact_by_address", return_value=contact),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        client.untag_resource.assert_called_once_with(arn="arn:contact", tagKeys=["remove"], aws_retry=True)
        client.tag_resource.assert_called_once_with(arn="arn:contact", tags={"keep": "new"}, aws_retry=True)
        client.create_email_contact.assert_not_called()

    def test_tag_update_rejects_invalid_tag_response(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {"tags": []}
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": {"keep": "new"},
            }
        )
        contact = {"address": "ops@example.com", "arn": "arn:contact", "name": "Operations"}
        with (
            patch.object(plugin, "get_contact_by_address", return_value=contact),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to list tags for AWS Notifications contact arn:contact: AWS returned an invalid response",
        )

    def test_create_rejects_invalid_response(self):
        client = Mock()
        client.create_email_contact.return_value = {}
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "get_contact_by_address", return_value=None),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to create AWS Notifications contact ops@example.com: AWS returned an invalid response",
        )

    def test_create_rejects_post_create_response_without_contact(self):
        client = Mock()
        client.create_email_contact.return_value = {"arn": "arn:new"}
        client.get_email_contact.return_value = {}
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "get_contact_by_address", return_value=None),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unable to get AWS Notifications contact arn:new: AWS returned an invalid response",
        )

    def test_contact_address_and_name_are_validated_before_api_calls(self):
        base = {"state": "present", "tags": None}
        cases = [
            (
                dict(base, email_address="invalid", name="Operations"),
                "email_address must be a valid email address of 6 to 254 characters",
            ),
            (
                dict(base, email_address="ops@@example.com", name="Operations"),
                "email_address must be a valid email address of 6 to 254 characters",
            ),
            (
                dict(base, email_address="ops @example.com", name="Operations"),
                "email_address must be a valid email address of 6 to 254 characters",
            ),
            (
                dict(base, email_address="ops@example.com", name=" "),
                "name must be 1 to 64 characters and contain at least one letter, digit, underscore, hyphen, period, or tilde",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_name_change_replaces_the_contact(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {"tags": {}}
        client.create_email_contact.return_value = {"arn": "arn:new"}
        client.get_email_contact.return_value = {
            "emailContact": {
                "address": "ops@example.com",
                "arn": "arn:new",
                "name": "New Name",
            }
        }
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "New Name",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "address": "ops@example.com",
            "arn": "arn:old",
            "name": "Old Name",
        }
        with (
            patch.object(plugin, "get_contact_by_address", return_value=current),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        client.delete_email_contact.assert_called_once_with(arn="arn:old", aws_retry=True)
        client.create_email_contact.assert_called_once_with(
            emailAddress="ops@example.com", name="New Name", aws_retry=True
        )

    def test_name_change_preserves_tags_when_tags_are_omitted(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {"tags": {"keep": "value"}}
        client.create_email_contact.return_value = {"arn": "arn:new"}
        client.get_email_contact.return_value = {
            "emailContact": {"address": "ops@example.com", "arn": "arn:new", "name": "New Name"}
        }
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "New Name",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {"address": "ops@example.com", "arn": "arn:old", "name": "Old Name"}
        with (
            patch.object(plugin, "get_contact_by_address", return_value=current),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        client.list_tags_for_resource.assert_called_once_with(arn="arn:old", aws_retry=True)
        client.create_email_contact.assert_called_once_with(
            emailAddress="ops@example.com",
            name="New Name",
            tags={"keep": "value"},
            aws_retry=True,
        )
        self.assertEqual(raised.exception.values["email_contact"]["tags"], {"keep": "value"})

    def test_check_mode_name_change_predicts_preserved_tags(self):
        client = Mock()
        client.list_tags_for_resource.return_value = {"tags": {"keep": "value"}}
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "New Name",
                "purge_tags": True,
                "tags": None,
            },
            check_mode=True,
        )
        current = {"address": "ops@example.com", "arn": "arn:old", "name": "Old Name"}
        with (
            patch.object(plugin, "get_contact_by_address", return_value=current),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["email_contact"],
            {"address": "ops@example.com", "name": "New Name", "tags": {"keep": "value"}},
        )
        client.delete_email_contact.assert_not_called()
        client.create_email_contact.assert_not_called()

    def test_new_contact_omits_empty_tags(self):
        client = Mock()
        client.create_email_contact.return_value = {"arn": "arn:new"}
        client.get_email_contact.return_value = {"emailContact": None}
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": {},
            }
        )
        with (
            patch.object(plugin, "get_contact_by_address", return_value=None),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)
        client.create_email_contact.assert_called_once_with(
            emailAddress="ops@example.com", name="Operations", aws_retry=True
        )

    def test_new_contact_tolerates_post_create_lookup_race(self):
        client = Mock()
        client.create_email_contact.return_value = {"arn": "arn:new"}
        client.get_email_contact.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not visible yet"}},
            "GetEmailContact",
        )
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "get_contact_by_address", return_value=None),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["email_contact"],
            {"address": "ops@example.com", "arn": "arn:new", "name": "Operations"},
        )

    def test_converged_contact_does_not_require_unused_operations(self):
        client = Mock()
        module = FakeModule(
            {
                "email_address": "ops@example.com",
                "name": "Operations",
                "purge_tags": True,
                "tags": None,
            }
        )
        contact = {
            "address": "ops@example.com",
            "arn": "arn:contact",
            "name": "Operations",
        }
        with (
            patch.object(plugin, "get_contact_by_address", return_value=contact),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertFalse(raised.exception.values["changed"])
        require.assert_not_called()
