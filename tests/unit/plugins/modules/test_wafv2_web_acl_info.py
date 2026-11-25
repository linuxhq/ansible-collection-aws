from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import wafv2 as wafv2_utils
from ansible_collections.linuxhq.aws.plugins.modules import wafv2_web_acl_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
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
    captured = assert_module_contract(plugin)

    assert captured["argument_spec"]["scope"]["choices"] == ["cloudfront", "regional"]


def test_custom_response_body_names_and_references_are_preserved():
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
    result, _require, _query = run(FakeModule(params(), client=acl_client(acl)), [SUMMARY])

    web_acl = result.values["web_acls"][0]
    bodies = web_acl["custom_response_bodies"]
    assert bodies == {
        "BlockPage": {"content": "denied", "content_type": "TEXT_PLAIN"},
        "block_page": {"content": "another body", "content_type": "TEXT_PLAIN"},
    }
    reference = web_acl["default_action"]["block"]["custom_response"]["custom_response_body_key"]
    assert bodies[reference]["content"] == "denied"


def test_challenge_javascript_sdk_injection_resource_types_are_preserved():
    acl = {
        "ARN": "arn:web-acl",
        "Id": "acl-1",
        "Name": "main",
        "AssociationConfig": {
            "RequestBody": {
                "CLOUDFRONT": {"DefaultSizeInspectionLimit": "KB_16"},
                "API_GATEWAY": {"DefaultSizeInspectionLimit": "KB_32"},
            },
            "ChallengeJavascriptSdkInjection": {"CLOUDFRONT": {}},
        },
    }
    result, _require, _query = run(FakeModule(params(), client=acl_client(acl)), [SUMMARY])

    assert result.values["web_acls"][0]["association_config"] == {
        "challenge_javascript_sdk_injection": {"CLOUDFRONT": {}},
        "request_body": {
            "CLOUDFRONT": {"default_size_inspection_limit": "KB_16"},
            "API_GATEWAY": {"default_size_inspection_limit": "KB_32"},
        },
    }


def test_tags_are_returned_with_their_case():
    client = acl_client(
        {"ARN": "arn:web-acl", "Id": "acl-1", "Name": "main"},
        [{"Key": "Name", "Value": "main"}, {"Key": "CostCenter", "Value": "A1"}],
    )
    result, require_client_methods, _query = run(FakeModule(params(), client=client), [SUMMARY])

    assert result.values["web_acls"][0]["tags"] == {"Name": "main", "CostCenter": "A1"}
    assert "list_tags_for_resource" in require_client_methods.call_args.args[3]


def test_regional_scope_is_uppercase_for_aws():
    _result, _require, query_list = run(FakeModule(params(), client=Mock()), [])

    assert query_list.call_args.kwargs["Scope"] == "REGIONAL"


def test_non_utf8_search_string_bytes_are_replaced():
    # Live: WAF stores and returns a SearchString of b"\xff\xfe"; lone surrogates make the controller fail the task.
    statement = {"ByteMatchStatement": {"SearchString": b"\xff\xfeadmin\xc3\xa9", "PositionalConstraint": "CONTAINS"}}
    acl = {"ARN": "arn:web-acl", "Rules": [{"Name": "rule", "Statement": statement}], **SUMMARY}
    result, _require, _query = run(FakeModule(params(id="acl-1"), client=acl_client(acl)), [SUMMARY])

    search_string = result.values["web_acls"][0]["rules"][0]["statement"]["byte_match_statement"]["search_string"]
    assert search_string == "��adminé"


def test_id_and_name_get_the_web_acl_without_listing():
    acl = {"ARN": "arn:web-acl", "DefaultAction": {"Allow": {}}, "Id": "acl-1", "Name": "main"}
    client = acl_client(acl)
    result, _require, query_list = run(FakeModule(params(id="acl-1", name="main"), client=client), [])

    query_list.assert_not_called()
    client.get_web_acl.assert_called_once_with(Id="acl-1", Name="main", Scope="REGIONAL", aws_retry=True)
    assert result.values["web_acls"] == [
        {"arn": "arn:web-acl", "default_action": {"allow": {}}, "id": "acl-1", "name": "main", "tags": {}}
    ]
