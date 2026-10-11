import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import ssm_document_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)


def params(**overrides):
    values = {"document_format": "JSON", "document_version": None, "filters": None, "name": None, "version_name": None}
    values.update(overrides)
    return values


def described(document_format="JSON"):
    return {"Document": {"DocumentFormat": document_format, "Name": "example"}}


def run(module, documents=None):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=documents or []) as query_list,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods, query_list


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert len(captured["mutually_exclusive"]) == 2
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_content_transform_returns_json_unchanged_and_text_as_is():
    assert plugin.content_transform('{"schemaVersion":"2.2"}') == {"schemaVersion": "2.2"}
    assert plugin.content_transform("not-json") == "not-json"
    assert plugin.content_transform(None) == {}


def test_empty_name_is_rejected():
    result, _require, _query = run(FakeModule(params(name="")))

    assert result.values["msg"] == "name must not be empty"


def test_version_name_omits_document_version_and_loads_content_and_tags():
    client = Mock()
    client.describe_document.return_value = described()
    client.get_document.return_value = {"Content": '{"schemaVersion":"2.2"}', "Name": "example"}
    client.list_tags_for_resource.return_value = {"TagList": [{"Key": "Name", "Value": "example"}]}
    module = FakeModule(params(name="example", version_name="production"), client=client)
    result, require_client_methods, _query = run(module)

    require_client_methods.assert_called_once_with(
        module,
        client,
        "Systems Manager",
        {
            "describe_document": ("Name", "VersionName"),
            "get_document": ("Name", "DocumentFormat", "VersionName"),
            "list_tags_for_resource": ("ResourceId", "ResourceType"),
        },
    )
    assert "DocumentVersion" not in client.get_document.call_args.kwargs
    assert client.get_document.call_args.kwargs["VersionName"] == "production"
    assert result.values["document"]["content"] == {"schemaVersion": "2.2"}
    assert result.values["document"]["tags"] == {"Name": "example"}


def test_content_keys_are_returned_unchanged():
    content = {
        "schemaVersion": "2.2",
        "parameters": {"Message": {"type": "String"}},
        "mainSteps": [{"action": "aws:executeScript", "inputs": {"InputPayload": {"Key_Name": 1}}}],
    }
    client = Mock()
    client.describe_document.return_value = described()
    client.get_document.return_value = {"Content": json.dumps(content), "Name": "example"}
    client.list_tags_for_resource.return_value = {"TagList": []}
    result, _require, _query = run(FakeModule(params(name="example"), client=client))

    assert result.values["documents"][0]["content"] == content


def test_filter_values_are_converted_to_strings():
    _result, _require, query_list = run(FakeModule(params(filters={"Owner": [123]}), client=Mock()))

    assert query_list.call_args.kwargs["Filters"] == [{"Key": "Owner", "Values": ["123"]}]


def test_rejects_malformed_document_identifier():
    result, _require, _query = run(FakeModule(params(), client=Mock()), [None])

    assert result.values["msg"] == "Unexpected response while listing AWS Systems Manager documents"


def test_rejects_malformed_get_response():
    client = Mock(describe_document=Mock(return_value=described()), get_document=Mock(return_value=None))
    result, _require, _query = run(FakeModule(params(name="example"), client=client))

    assert result.values["msg"] == "Unexpected response while getting AWS Systems Manager document example"


def test_rejects_malformed_tags():
    client = Mock(
        describe_document=Mock(return_value=described()),
        get_document=Mock(return_value={"Content": "{}", "Name": "example"}),
        list_tags_for_resource=Mock(return_value={"TagList": [None]}),
    )
    result, _require, _query = run(FakeModule(params(name="example"), client=client))

    assert result.values["msg"] == "Unexpected response while listing tags for AWS Systems Manager document example"


def missing_version_error(operation="GetDocument"):
    return ClientError({"Error": {"Code": "InvalidDocumentVersion", "Message": "no"}}, operation)


@pytest.mark.parametrize("version", [{"document_version": "3"}, {"version_name": "production"}])
def test_listed_documents_without_the_requested_version_are_omitted(version):
    client = Mock(
        get_document=Mock(side_effect=[missing_version_error(), {"Content": "{}", "Name": "second"}]),
        list_tags_for_resource=Mock(return_value={"TagList": []}),
    )
    module = FakeModule(params(**version), client=client)
    result, _require, _query = run(module, [{"Name": "first"}, {"Name": "second"}])

    assert [document["name"] for document in result.values["documents"]] == ["second"]


def test_named_document_without_the_requested_version_returns_empty():
    client = Mock(describe_document=Mock(side_effect=missing_version_error("DescribeDocument")))
    result, _require, _query = run(FakeModule(params(name="example", version_name="production"), client=client))

    assert result.values["document"] == {}
    assert result.values["documents"] == []
    client.describe_document.assert_called_once_with(Name="example", VersionName="production", aws_retry=True)
    client.get_document.assert_not_called()
    client.list_tags_for_resource.assert_not_called()


@pytest.mark.parametrize(
    ("document_format", "requested", "available"),
    [
        ("JSON", "JSON", True),
        ("JSON", "YAML", True),
        ("YAML", "JSON", True),
        ("JSON", "TEXT", False),
        ("YAML", "TEXT", False),
        ("TEXT", "TEXT", True),
        ("TEXT", "JSON", False),
        ("TEXT", "YAML", False),
    ],
)
def test_format_available_only_converts_between_json_and_yaml(document_format, requested, available):
    assert plugin.format_available(document_format, requested) is available


def test_listed_documents_that_cannot_be_served_in_the_requested_format_are_skipped():
    client = Mock(
        get_document=Mock(return_value={"Content": "echo", "DocumentFormat": "TEXT", "Name": "text"}),
        list_tags_for_resource=Mock(return_value={"TagList": []}),
    )
    identifiers = [
        {"DocumentFormat": "JSON", "Name": "json"},
        {"DocumentFormat": "YAML", "Name": "yaml"},
        {"DocumentFormat": "TEXT", "Name": "text"},
    ]
    result, _require, _query = run(FakeModule(params(document_format="TEXT"), client=client), identifiers)

    assert [document["name"] for document in result.values["documents"]] == ["text"]
    client.get_document.assert_called_once_with(
        DocumentFormat="TEXT", DocumentVersion="$LATEST", Name="text", aws_retry=True
    )


def test_named_document_that_cannot_be_served_in_the_requested_format_returns_empty():
    client = Mock(describe_document=Mock(return_value=described("JSON")))
    result, _require, _query = run(FakeModule(params(name="example", document_format="TEXT"), client=client))

    assert result.values["document"] == {}
    assert result.values["documents"] == []
    client.describe_document.assert_called_once_with(DocumentVersion="$LATEST", Name="example", aws_retry=True)
    client.get_document.assert_not_called()


def test_named_document_rejects_malformed_describe_response():
    client = Mock(describe_document=Mock(return_value={"Document": {}}))
    result, _require, _query = run(FakeModule(params(name="example"), client=client))

    assert result.values["msg"] == "Unexpected response while describing AWS Systems Manager document example"
    client.get_document.assert_not_called()
