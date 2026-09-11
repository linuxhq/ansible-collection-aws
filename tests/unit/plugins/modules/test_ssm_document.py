import json
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

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

    def test_get_document_rejects_malformed_content(self):
        responses = (None, {"Content": "not-json"}, {"Content": "[]"})
        for response in responses:
            with self.subTest(response=response):
                client = Mock(get_document=Mock(return_value=response))
                module = FakeModule({"document_version": "$LATEST", "name": "example"})
                with self.assertRaises(ModuleFail) as raised:
                    plugin.get_document(client, module)

                self.assertIn("Unexpected", raised.exception.values["msg"])

    def test_get_document_rejects_malformed_tags(self):
        client = Mock(
            get_document=Mock(return_value={"Content": "{}"}),
            list_tags_for_resource=Mock(return_value={"TagList": [None]}),
        )
        module = FakeModule({"document_version": "$LATEST", "name": "example"})
        with self.assertRaises(ModuleFail) as raised:
            plugin.get_document(client, module, include_tags=True)

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while listing tags for AWS Systems Manager document example",
        )

    def test_create_rejects_malformed_response(self):
        client = Mock(create_document=Mock(return_value={"DocumentDescription": None}))
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
        with (
            patch.object(plugin, "get_document", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)

        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Systems Manager did not return the created document example",
        )


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("payload_key", ["InputPayload", "inputPayload", "input_payload"])
def test_ssm_document_preserves_script_payload_keys(check_mode, existing, payload_key):
    payload = {
        "myValue": "camel",
        "my_value": "snake",
        "nestedData": {"SomeKey": 1, "some_key": 2},
        "items": [{"AnotherKey": False, "another_key": None}, ["unchanged", 3]],
    }
    content = {
        "schemaVersion": "0.3",
        "mainSteps": [
            {
                "name": "run",
                "action": "aws:executeScript",
                "inputs": {
                    "Runtime": "python3.11",
                    "Handler": "handler",
                    payload_key: payload,
                    "Script": "def handler(events, context):\n    return events['my_value']",
                },
            }
        ],
    }
    client = Mock(
        create_document=Mock(
            return_value={
                "DocumentDescription": {"Name": "review", "DocumentType": "Automation", "DocumentVersion": "1"}
            }
        )
    )
    module = FakeModule(
        {
            "name": "review",
            "tags": None,
            "purge_tags": True,
            "content": content,
            "document_type": "Automation",
            "document_version": "$LATEST",
        },
        check_mode=check_mode,
    )
    current = {"Name": "review", "DocumentType": "Automation", "Content": json.dumps(content)} if existing else None
    with patch.object(plugin, "get_document", return_value=current), pytest.raises(ModuleExit) as result:
        plugin.ensure_present(client, module)

    returned = result.value.values["document"]["content"]["main_steps"][0]["inputs"]["input_payload"]
    assert returned == payload
    if check_mode or existing:
        client.create_document.assert_not_called()
        client.update_document.assert_not_called()
    else:
        created = json.loads(client.create_document.call_args.kwargs["Content"])
        normalized_payload_key = "InputPayload" if payload_key == "InputPayload" else "inputPayload"
        assert created["mainSteps"][0]["inputs"][normalized_payload_key] == payload
        assert created["mainSteps"][0]["inputs"]["Script"] == content["mainSteps"][0]["inputs"]["Script"]


@pytest.mark.parametrize("existing_key", ["my_value", "myValue"])
def test_script_payload_keys_are_compared_exactly(existing_key):
    content = {
        "schemaVersion": "0.3",
        "mainSteps": [
            {
                "name": "run",
                "action": "aws:executeScript",
                "inputs": {
                    "Runtime": "python3.11",
                    "Handler": "handler",
                    "Script": "def handler(events, context):\n    return events['my_value']",
                    "InputPayload": {"my_value": "value"},
                },
            }
        ],
    }
    existing_content = json.loads(json.dumps(content))
    existing_content["mainSteps"][0]["inputs"]["InputPayload"] = {existing_key: "value"}
    current = {
        "Name": "review",
        "DocumentType": "Automation",
        "DocumentVersion": "1",
        "Content": json.dumps(existing_content),
    }
    client = Mock(update_document=Mock(return_value={"DocumentDescription": {"DocumentVersion": "2"}}))
    module = FakeModule(
        {
            "name": "review",
            "document_type": "Automation",
            "document_version": "$LATEST",
            "content": content,
            "tags": None,
            "purge_tags": True,
        }
    )
    with (
        patch.object(plugin, "get_document", return_value=current),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is (existing_key != "my_value")
    if existing_key == "my_value":
        client.update_document.assert_not_called()
        client.update_document_default_version.assert_not_called()
    else:
        submitted = json.loads(client.update_document.call_args.kwargs["Content"])
        assert submitted == content
        client.update_document_default_version.assert_called_once_with(
            DocumentVersion="2",
            Name="review",
            aws_retry=True,
        )
