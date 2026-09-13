import json
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ssm_document_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
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
        content = {"schemaVersion": "2.2"}
        assert plugin.content_transform(content) is content

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

    def test_filter_values_are_converted_to_strings(self):
        module = FakeModule(
            {
                "document_format": "JSON",
                "document_version": None,
                "filters": {"Owner": [123]},
                "name": None,
                "version_name": None,
            },
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]) as query,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(query.call_args.kwargs["Filters"], [{"Key": "Owner", "Values": ["123"]}])

    def test_rejects_malformed_document_identifier(self):
        module = FakeModule(
            {
                "document_format": "JSON",
                "document_version": None,
                "filters": None,
                "name": None,
                "version_name": None,
            },
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[None]),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while listing AWS Systems Manager documents",
        )

    def test_rejects_malformed_get_response(self):
        client = Mock(get_document=Mock(return_value=None))
        module = FakeModule(
            {
                "document_format": "JSON",
                "document_version": None,
                "filters": None,
                "name": "example",
                "version_name": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS Systems Manager document example",
        )

    def test_rejects_malformed_tags(self):
        client = Mock(
            get_document=Mock(return_value={"Content": "{}", "Name": "example"}),
            list_tags_for_resource=Mock(return_value={"TagList": [None]}),
        )
        module = FakeModule(
            {
                "document_format": "JSON",
                "document_version": None,
                "filters": None,
                "name": "example",
                "version_name": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while listing tags for AWS Systems Manager document example",
        )


@pytest.mark.parametrize("payload_key", ["InputPayload", "inputPayload", "input_payload"])
def test_document_result_preserves_script_payload(payload_key):
    payload = {"CustomerID": "one", "customer_id": "two", "Items": [{"NestedKey": "value"}]}
    content = {"schemaVersion": "0.3", "mainSteps": [{"inputs": {payload_key: payload}}]}
    client = Mock()
    client.get_document.return_value = {"Name": "example", "Content": json.dumps(content)}
    client.list_tags_for_resource.return_value = {"TagList": []}
    module = FakeModule(
        {"name": "example", "document_format": "JSON", "document_version": None, "version_name": None, "filters": None},
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    result = raised.value.values["document"]["content"]
    assert result["schema_version"] == "0.3"
    assert result["main_steps"][0]["inputs"]["input_payload"] == payload


def test_document_content_preserves_parameter_names_and_round_trips():
    content = {
        "schemaVersion": "2.2",
        "parameters": {
            "Message": {"type": "String", "default": "Hello", "allowedValues": ["Hello"]},
            "message": {"type": "String", "default": "World"},
        },
        "mainSteps": [
            {
                "action": "aws:runShellScript",
                "name": "printMessage",
                "inputs": {"runCommand": ["echo {{Message}} {{message}}"]},
            }
        ],
    }
    result = plugin.content_transform(json.dumps(content))
    assert set(result["parameters"]) == {"Message", "message"}
    assert result["parameters"]["Message"]["allowed_values"] == ["Hello"]
    assert result["main_steps"][0]["inputs"]["run_command"] == ["echo {{Message}} {{message}}"]
    assert plugin.normalize_document_content(result) == content


@pytest.mark.parametrize(
    "parameter_type,default",
    [
        ("StringMap", {"tenant_id": "alpha", "tenantId": "beta"}),
        ("MapList", [{"tenant_id": "alpha", "tenantId": "beta"}]),
    ],
)
def test_document_info_preserves_map_defaults(parameter_type, default):
    content = {
        "schemaVersion": "0.3",
        "parameters": {"Payload": {"type": parameter_type, "default": default, "maxItems": 2}},
    }
    result = plugin.content_transform(json.dumps(content))
    assert result["parameters"]["Payload"]["default"] == default
    assert result["parameters"]["Payload"]["max_items"] == 2
    assert plugin.normalize_document_content(result) == content


@pytest.mark.parametrize("document_type", ["ApplicationConfiguration", "ApplicationConfigurationSchema"])
def test_application_document_info_preserves_content(document_type):
    content = {
        "properties": {"feature_enabled": {"maxLength": 10}},
        "required": ["feature_enabled"],
        "featureEnabled": True,
        "feature_enabled": False,
    }
    client = Mock()
    client.get_document.return_value = {
        "Name": "example",
        "DocumentType": document_type,
        "Content": json.dumps(content),
    }
    client.list_tags_for_resource.return_value = {"TagList": []}
    module = FakeModule(
        {
            "name": "example",
            "document_format": "JSON",
            "document_version": None,
            "version_name": None,
            "filters": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    assert result.value.values["document"]["content"] == content
    assert result.value.values["documents"][0]["content"] == content
