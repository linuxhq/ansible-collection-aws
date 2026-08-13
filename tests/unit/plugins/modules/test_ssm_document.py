from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ssm_document as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class SsmDocumentTests(TestCase):
    def test_absent_tolerates_document_disappearing_during_delete(self):
        client = Mock()
        client.delete_document.side_effect = plugin.ClientError(
            {"Error": {"Code": "InvalidDocument", "Message": "gone"}},
            "DeleteDocument",
        )
        module = FakeModule({"name": "document"})
        with (
            patch.object(plugin, "get_document", return_value={"Name": "document"}),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_if"] == [("state", "present", ["content", "document_type"])]

    def test_document_content_accepts_json_or_mapping(self):
        assert plugin.document_content({"Content": '{"schemaVersion":"2.2"}'}) == {"schemaVersion": "2.2"}
        content = {"schemaVersion": "2.2"}
        assert plugin.document_content({"Content": content}) is content
        assert plugin.document_content(None) == {}

    def test_content_update_promotes_the_new_default_version(self):
        client = Mock()
        client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2"}}
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Command",
                "document_version": "$LATEST",
                "name": "example",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "Content": '{"schemaVersion":"1.2"}',
            "DocumentType": "Command",
            "Name": "example",
        }
        updated = dict(current, Content='{"schemaVersion":"2.2"}')
        with (
            patch.object(plugin, "get_document", side_effect=[current, updated]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            client.update_document.call_args.kwargs["Content"],
            '{"schemaVersion":"2.2"}',
        )
        client.update_document_default_version.assert_called_once_with(
            DocumentVersion="2", Name="example", aws_retry=True
        )

    def test_default_version_updates_latest_instead_of_the_older_default(self):
        client = Mock()
        client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "3"}}
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Command",
                "document_version": "$DEFAULT",
                "name": "example",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "Content": '{"schemaVersion":"1.2"}',
            "DocumentType": "Command",
            "DocumentVersion": "1",
            "Name": "example",
        }
        latest = dict(current, DocumentVersion="2")
        updated = dict(current, Content='{"schemaVersion":"2.2"}', DocumentVersion="3")
        with (
            patch.object(plugin, "get_document", side_effect=[current, latest, updated]),
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(client.update_document.call_args.kwargs["DocumentVersion"], "$LATEST")
        client.update_document_default_version.assert_called_once_with(
            DocumentVersion="3", Name="example", aws_retry=True
        )

    def test_default_version_promotes_matching_latest_without_duplicate_update(self):
        client = Mock()
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Command",
                "document_version": "$DEFAULT",
                "name": "example",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "Content": '{"schemaVersion":"1.2"}',
            "DocumentType": "Command",
            "DocumentVersion": "1",
            "Name": "example",
        }
        latest = dict(
            current,
            Content='{"schemaVersion":"2.2"}',
            DocumentVersion="2",
        )
        with (
            patch.object(plugin, "get_document", side_effect=[current, latest, latest]),
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        client.update_document.assert_not_called()
        client.update_document_default_version.assert_called_once_with(
            DocumentVersion="2", Name="example", aws_retry=True
        )

    def test_update_result_ignores_stale_default_version_refresh(self):
        client = Mock()
        client.update_document.return_value = {"DocumentDescription": {"DocumentVersion": "2", "Name": "example"}}
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Command",
                "document_version": "$DEFAULT",
                "name": "example",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "Content": '{"schemaVersion":"1.2"}',
            "DocumentType": "Command",
            "DocumentVersion": "1",
            "Name": "example",
        }
        with (
            patch.object(plugin, "get_document", side_effect=[current, current, current]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["document"]["content"],
            {"schema_version": "2.2"},
        )
        self.assertEqual(raised.exception.values["document"]["document_version"], "2")

    def test_update_fails_when_aws_omits_the_new_document_version(self):
        client = Mock()
        client.update_document.return_value = {"DocumentDescription": {}}
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Command",
                "document_version": "$LATEST",
                "name": "example",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "Content": '{"schemaVersion":"1.2"}',
            "DocumentType": "Command",
            "Name": "example",
        }

        with (
            patch.object(plugin, "get_document", return_value=current),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertIn("no document version", raised.exception.values["msg"])
        client.update_document_default_version.assert_not_called()

    def test_existing_document_type_is_immutable(self):
        client = Mock()
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Session",
                "document_version": "$LATEST",
                "name": "example",
                "purge_tags": True,
                "tags": None,
            }
        )
        current = {
            "Content": '{"schemaVersion":"2.2"}',
            "DocumentType": "Command",
            "Name": "example",
        }
        with (
            patch.object(plugin, "get_document", return_value=current),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertIn("immutable fields differ", raised.exception.values["msg"])
        client.update_document.assert_not_called()

    def test_new_document_serializes_content_and_tags_for_aws(self):
        client = Mock()
        client.create_document.return_value = {
            "DocumentDescription": {
                "DocumentVersion": "1",
                "Name": "example",
            }
        }
        module = FakeModule(
            {
                "content": {"schema_version": "2.2"},
                "document_type": "Command",
                "document_version": "$LATEST",
                "name": "example",
                "purge_tags": True,
                "tags": {"Name": "example"},
            }
        )
        with (
            patch.object(plugin, "get_document", side_effect=[None, None]),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertEqual(
            raised.exception.values["document"],
            {
                "content": {"schema_version": "2.2"},
                "document_version": "1",
                "name": "example",
                "tags": {"Name": "example"},
            },
        )
        self.assertTrue(raised.exception.values["changed"])
        client.create_document.assert_called_once_with(
            Content='{"schemaVersion":"2.2"}',
            DocumentFormat="JSON",
            DocumentType="Command",
            Name="example",
            Tags=[{"Key": "Name", "Value": "example"}],
            aws_retry=True,
        )
