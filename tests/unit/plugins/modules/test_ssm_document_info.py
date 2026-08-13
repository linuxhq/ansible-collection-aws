from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ssm_document_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
    assert_module_rejects,
)


class SsmDocumentInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert len(options["mutually_exclusive"]) == 2

    def test_content_transform_handles_json_text_and_empty_values(self):
        assert plugin.content_transform('{"schemaVersion":"2.2"}') == {"schema_version": "2.2"}
        assert plugin.content_transform("not-json") == "not-json"
        assert plugin.content_transform(None) == {}

    def test_empty_name_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "document_format": "JSON",
                "document_version": None,
                "filters": None,
                "name": "",
                "version_name": None,
            },
            "name must not be empty",
        )

    def test_version_name_omits_document_version_and_loads_content_and_tags(self):
        client = Mock()
        client.get_document.return_value = {
            "Content": '{"schemaVersion":"2.2"}',
            "Name": "example",
        }
        client.list_tags_for_resource.return_value = {"TagList": [{"Key": "Name", "Value": "example"}]}
        module = FakeModule(
            {
                "document_format": "JSON",
                "document_version": None,
                "filters": None,
                "name": "example",
                "version_name": "production",
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        require_methods.assert_called_once_with(
            module,
            client,
            "Systems Manager",
            {
                "get_document": ("Name", "DocumentFormat", "VersionName"),
                "list_tags_for_resource": ("ResourceId", "ResourceType"),
            },
        )
        self.assertNotIn("DocumentVersion", client.get_document.call_args.kwargs)
        self.assertEqual(client.get_document.call_args.kwargs["VersionName"], "production")
        document = raised.exception.values["document"]
        self.assertEqual(document["content"]["schema_version"], "2.2")
        self.assertEqual(document["tags"], {"Name": "example"})
