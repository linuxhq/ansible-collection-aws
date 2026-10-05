from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import wafv2_ip_set_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
)

IP_SET = {"Addresses": [], "ARN": "arn:ip-set", "Id": "wanted", "IPAddressVersion": "IPV4", "Name": "target"}


def params(**overrides):
    values = {"id": None, "name": None, "scope": "regional"}
    values.update(overrides)
    return values


def ip_set_client(tags=None):
    return Mock(
        get_ip_set=Mock(return_value={"IPSet": IP_SET}),
        list_tags_for_resource=Mock(return_value={"TagInfoForResource": {"TagList": tags or []}}),
    )


def run(module, summaries=None):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(plugin, "query_list", return_value=summaries) as query_list,
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


def test_cloudfront_scope_is_uppercase_for_aws():
    _result, _require, query_list = run(FakeModule(params(scope="cloudfront"), client=Mock()), [])

    assert query_list.call_args.kwargs["Scope"] == "CLOUDFRONT"


def test_cloudfront_scope_outside_us_east_1_fails_before_aws():
    module = FakeModule(params(scope="cloudfront"), client=Mock(), region="us-west-2")
    result, require_client_methods, query_list = run(module, [])

    assert result.values["msg"] == "scope cloudfront requires the us-east-1 region, not us-west-2"
    require_client_methods.assert_not_called()
    query_list.assert_not_called()


@pytest.mark.parametrize("option", ["id", "name"])
def test_rejects_empty_filters(option):
    result, _require, _query = run(FakeModule(params(**{option: ""})))

    assert result.values["msg"] == f"{option} must not be empty"


@pytest.mark.parametrize(
    ("summary", "message"),
    [(None, "Unexpected response while listing"), ({}, "invalid ID"), ({"Id": "id-1"}, "invalid name")],
)
def test_rejects_malformed_selected_summary(summary, message):
    result, _require, _query = run(FakeModule(params(), client=Mock()), [summary])

    assert message in result.values["msg"]


def test_rejects_malformed_summary_list():
    result, _require, _query = run(FakeModule(params(), client=Mock()), None)

    assert result.values["msg"] == "Unexpected response while listing AWS WAFv2 IP sets for REGIONAL"


def test_filtered_lookup_skips_malformed_unmatched_summary():
    result, _require, _query = run(
        FakeModule(params(id="wanted"), client=ip_set_client()), [None, {"Id": "wanted", "Name": "target"}]
    )

    assert result.values["ip_sets"][0]["id"] == "wanted"


def test_missing_name_returns_empty_list():
    result, _require, _query = run(FakeModule(params(name="missing"), client=ip_set_client()), [IP_SET])

    assert result.values["ip_sets"] == []


def test_tags_are_returned_with_their_case():
    client = ip_set_client([{"Key": "Name", "Value": "target"}, {"Key": "CostCenter", "Value": "A1"}])
    result, require_client_methods, _query = run(FakeModule(params(), client=client), [IP_SET])

    assert result.values["ip_sets"][0]["tags"] == {"Name": "target", "CostCenter": "A1"}
    client.list_tags_for_resource.assert_called_once_with(ResourceARN="arn:ip-set", aws_retry=True)
    assert "list_tags_for_resource" in require_client_methods.call_args.args[3]


def test_tags_are_paginated():
    client = ip_set_client()
    client.list_tags_for_resource.side_effect = [
        {"TagInfoForResource": {"TagList": [{"Key": "A", "Value": "1"}]}, "NextMarker": "page-2"},
        {"TagInfoForResource": {"TagList": [{"Key": "B", "Value": "2"}]}},
    ]
    result, _require, _query = run(FakeModule(params(), client=client), [IP_SET])

    assert result.values["ip_sets"][0]["tags"] == {"A": "1", "B": "2"}
    assert client.list_tags_for_resource.call_args.kwargs["NextMarker"] == "page-2"


def test_ip_set_deleted_before_its_tags_are_read_is_skipped():
    client = ip_set_client()
    client.list_tags_for_resource.side_effect = ClientError(
        {"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}}, "ListTagsForResource"
    )
    result, _require, _query = run(FakeModule(params(), client=client), [IP_SET])

    assert result.values["ip_sets"] == []


@pytest.mark.parametrize(
    ("client", "message"),
    [
        (Mock(get_ip_set=Mock(return_value={})), "Unexpected response while getting AWS WAFv2 IP set target/wanted"),
        (
            Mock(
                get_ip_set=Mock(return_value={"IPSet": IP_SET}),
                list_tags_for_resource=Mock(return_value={"TagInfoForResource": {"TagList": [None]}}),
            ),
            "Unexpected response while listing tags for AWS WAFv2 IP set target/wanted",
        ),
    ],
)
def test_rejects_malformed_responses(client, message):
    result, _require, _query = run(FakeModule(params(), client=client), [{"Id": "wanted", "Name": "target"}])

    assert result.values["msg"] == message


def test_id_and_name_get_the_ip_set_without_listing():
    client = ip_set_client()
    result, _require, query_list = run(FakeModule(params(id="wanted", name="target"), client=client), [])

    query_list.assert_not_called()
    client.get_ip_set.assert_called_once_with(Id="wanted", Name="target", Scope="REGIONAL", aws_retry=True)
    assert result.values["ip_sets"] == [
        {
            "addresses": [],
            "arn": "arn:ip-set",
            "id": "wanted",
            "ip_address_version": "IPV4",
            "name": "target",
            "tags": {},
        }
    ]


def test_id_and_name_for_missing_ip_set_return_empty_list():
    client = ip_set_client()
    client.get_ip_set.side_effect = ClientError(
        {"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}}, "GetIPSet"
    )
    result, _require, query_list = run(FakeModule(params(id="wanted", name="missing"), client=client), [])

    query_list.assert_not_called()
    assert result.values["ip_sets"] == []
