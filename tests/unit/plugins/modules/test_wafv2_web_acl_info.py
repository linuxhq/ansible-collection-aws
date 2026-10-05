from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import wafv2 as wafv2_utils
from ansible_collections.linuxhq.aws.plugins.modules import wafv2_web_acl_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

SUMMARY = {"Id": "acl-1", "Name": "main"}


def params(**overrides):
    values = {"id": None, "name": None, "scope": "regional"}
    values.update(overrides)
    return values


def acl_client(acl, tags=None):
    return Mock(
        get_web_acl=Mock(return_value={"WebACL": acl}),
        list_tags_for_resource=Mock(return_value={"TagInfoForResource": {"TagList": tags or []}}),
    )


def run(module, summaries=None):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(wafv2_utils, "query_list", return_value=summaries) as query_list,
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
    assert captured["argument_spec"]["scope"]["choices"] == ["cloudfront", "regional"]
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


@pytest.mark.parametrize("filters", [{"id": "acl-1"}, {"name": "main"}, {}])
def test_custom_response_body_names_and_references_are_preserved(filters):
    acl = {
        "ARN": "arn:web-acl",
        "Id": "acl-1",
        "Name": "main",
        "CustomResponseBodies": {
            "BlockPage": {"Content": "denied", "ContentType": "TEXT_PLAIN"},
            "block_page": {"Content": "another body", "ContentType": "TEXT_PLAIN"},
        },
        "DefaultAction": {"Block": {"CustomResponse": {"ResponseCode": 403, "CustomResponseBodyKey": "BlockPage"}}},
    }
    result, _require, _query = run(FakeModule(params(**filters), client=acl_client(acl)), [SUMMARY])

    web_acl = result.values["web_acls"][0]
    bodies = web_acl["custom_response_bodies"]
    assert bodies == {
        "BlockPage": {"content": "denied", "content_type": "TEXT_PLAIN"},
        "block_page": {"content": "another body", "content_type": "TEXT_PLAIN"},
    }
    reference = web_acl["default_action"]["block"]["custom_response"]["custom_response_body_key"]
    assert bodies[reference]["content"] == "denied"


def test_request_body_resource_types_are_preserved():
    acl = {
        "ARN": "arn:web-acl",
        "Id": "acl-1",
        "Name": "main",
        "AssociationConfig": {
            "RequestBody": {
                "CLOUDFRONT": {"DefaultSizeInspectionLimit": "KB_16"},
                "API_GATEWAY": {"DefaultSizeInspectionLimit": "KB_32"},
            }
        },
    }
    result, _require, _query = run(FakeModule(params(), client=acl_client(acl)), [SUMMARY])

    assert result.values["web_acls"][0]["association_config"] == {
        "request_body": {
            "CLOUDFRONT": {"default_size_inspection_limit": "KB_16"},
            "API_GATEWAY": {"default_size_inspection_limit": "KB_32"},
        }
    }


def test_tags_are_returned_with_their_case():
    client = acl_client(
        {"ARN": "arn:web-acl", "Id": "acl-1", "Name": "main"},
        [{"Key": "Name", "Value": "main"}, {"Key": "CostCenter", "Value": "A1"}],
    )
    result, require_client_methods, _query = run(FakeModule(params(), client=client), [SUMMARY])

    assert result.values["web_acls"][0]["tags"] == {"Name": "main", "CostCenter": "A1"}
    client.list_tags_for_resource.assert_called_once_with(ResourceARN="arn:web-acl", aws_retry=True)
    assert "list_tags_for_resource" in require_client_methods.call_args.args[3]


def test_tags_are_paginated():
    client = acl_client({"ARN": "arn:web-acl", "Id": "acl-1", "Name": "main"})
    client.list_tags_for_resource.side_effect = [
        {"TagInfoForResource": {"TagList": [{"Key": "A", "Value": "1"}]}, "NextMarker": "page-2"},
        {"TagInfoForResource": {"TagList": [{"Key": "B", "Value": "2"}]}},
    ]
    result, _require, _query = run(FakeModule(params(), client=client), [SUMMARY])

    assert result.values["web_acls"][0]["tags"] == {"A": "1", "B": "2"}
    assert client.list_tags_for_resource.call_args.kwargs["NextMarker"] == "page-2"


def test_web_acl_deleted_before_its_tags_are_read_is_skipped():
    client = acl_client({"ARN": "arn:web-acl", "Id": "acl-1", "Name": "main"})
    client.list_tags_for_resource.side_effect = ClientError(
        {"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}}, "ListTagsForResource"
    )
    result, _require, _query = run(FakeModule(params(), client=client), [SUMMARY])

    assert result.values["web_acls"] == []


def test_regional_scope_is_uppercase_for_aws():
    _result, _require, query_list = run(FakeModule(params(), client=Mock()), [])

    assert query_list.call_args.kwargs["Scope"] == "REGIONAL"


def test_cloudfront_scope_outside_us_east_1_fails_before_aws():
    module = FakeModule(params(scope="cloudfront"), client=Mock(), region="us-west-2")
    result, require_client_methods, query_list = run(module, [])

    assert result.values["msg"] == "scope cloudfront requires the us-east-1 region, not us-west-2"
    require_client_methods.assert_not_called()
    query_list.assert_not_called()


def test_byte_values_are_returned_as_json_safe_text():
    acl = {"ARN": "arn:web-acl", "CustomResponseBodies": {"body": {"Content": bytearray(b"hello")}}, **SUMMARY}
    result, _require, _query = run(FakeModule(params(id="acl-1"), client=acl_client(acl)), [SUMMARY])

    assert result.values["web_acls"][0]["custom_response_bodies"]["body"]["content"] == "hello"


@pytest.mark.parametrize("option", ["id", "name"])
def test_rejects_empty_filters(option):
    result, _require, _query = run(FakeModule(params(**{option: ""})))

    assert result.values["msg"] == f"{option} must not be empty"


def test_rejects_malformed_summary_list():
    result, _require, _query = run(FakeModule(params(), client=Mock()), None)

    assert "Unexpected response while listing" in result.values["msg"]


@pytest.mark.parametrize(
    ("summary", "message"),
    [(None, "Unexpected response while listing"), ({}, "invalid ID"), ({"Id": "acl-1"}, "invalid name")],
)
def test_rejects_malformed_selected_summary(summary, message):
    result, _require, _query = run(FakeModule(params(), client=Mock()), [summary])

    assert message in result.values["msg"]


def test_filtered_lookup_skips_malformed_unmatched_summary():
    acl = {
        "ARN": "arn:web-acl",
        "DefaultAction": {"Allow": {}},
        "Id": "wanted",
        "Name": "target",
        "VisibilityConfig": {},
    }
    result, _require, _query = run(
        FakeModule(params(id="wanted"), client=acl_client(acl)), [None, {"Id": "wanted", "Name": "target"}]
    )

    assert result.values["web_acls"][0]["id"] == "wanted"


def test_missing_name_returns_empty_list():
    result, _require, _query = run(FakeModule(params(name="missing"), client=Mock()), [SUMMARY])

    assert result.values["web_acls"] == []


def test_rejects_malformed_web_acl_response():
    client = Mock(get_web_acl=Mock(return_value={}))
    result, _require, _query = run(FakeModule(params(), client=client), [SUMMARY])

    assert result.values["msg"] == "Unexpected response while getting AWS WAFv2 web ACL main/acl-1"


def test_id_and_name_get_the_web_acl_without_listing():
    acl = {"ARN": "arn:web-acl", "DefaultAction": {"Allow": {}}, "Id": "acl-1", "Name": "main"}
    client = acl_client(acl)
    result, _require, query_list = run(FakeModule(params(id="acl-1", name="main"), client=client), [])

    query_list.assert_not_called()
    client.get_web_acl.assert_called_once_with(Id="acl-1", Name="main", Scope="REGIONAL", aws_retry=True)
    assert result.values["web_acls"] == [
        {"arn": "arn:web-acl", "default_action": {"allow": {}}, "id": "acl-1", "name": "main", "tags": {}}
    ]


def test_id_and_name_for_missing_web_acl_return_empty_list():
    client = Mock()
    client.get_web_acl.side_effect = ClientError(
        {"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}}, "GetWebACL"
    )
    result, _require, query_list = run(FakeModule(params(id="acl-1", name="missing"), client=client), [])

    query_list.assert_not_called()
    assert result.values["web_acls"] == []
