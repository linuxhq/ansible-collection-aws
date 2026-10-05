from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import wafv2
from ansible_collections.linuxhq.aws.plugins.module_utils.wafv2 import get_resource_tags
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail

RESOURCE = {"ARN": "arn:waf", "Id": "id-1", "Name": "main"}


def test_tags_are_returned_with_their_case():
    client = Mock(
        list_tags_for_resource=Mock(
            return_value={
                "TagInfoForResource": {
                    "TagList": [{"Key": "Name", "Value": "main"}, {"Key": "CostCenter", "Value": "A1"}]
                }
            }
        )
    )

    assert get_resource_tags(client, FakeModule({}), RESOURCE, "IP set") == {"Name": "main", "CostCenter": "A1"}
    client.list_tags_for_resource.assert_called_once_with(ResourceARN="arn:waf", aws_retry=True)


def test_tags_are_paginated():
    client = Mock()
    client.list_tags_for_resource.side_effect = [
        {"TagInfoForResource": {"TagList": [{"Key": "A", "Value": "1"}]}, "NextMarker": "page-2"},
        {"TagInfoForResource": {"TagList": [{"Key": "B", "Value": "2"}]}},
    ]

    assert get_resource_tags(client, FakeModule({}), RESOURCE, "web ACL") == {"A": "1", "B": "2"}
    assert client.list_tags_for_resource.call_args.kwargs == {
        "ResourceARN": "arn:waf",
        "NextMarker": "page-2",
        "aws_retry": True,
    }


def test_deleted_resource_returns_none():
    client = Mock()
    client.list_tags_for_resource.side_effect = ClientError(
        {"Error": {"Code": "WAFNonexistentItemException", "Message": "gone"}}, "ListTagsForResource"
    )

    assert get_resource_tags(client, FakeModule({}), RESOURCE, "IP set") is None


@pytest.mark.parametrize("response", [[], {"TagInfoForResource": []}, {"TagInfoForResource": {"TagList": [None]}}])
def test_rejects_invalid_responses(response):
    client = Mock(list_tags_for_resource=Mock(return_value=response))
    with pytest.raises(ModuleFail) as raised:
        get_resource_tags(client, FakeModule({}), RESOURCE, "web ACL")

    assert raised.value.values["msg"] == "Unexpected response while listing tags for AWS WAFv2 web ACL main/id-1"


def test_errors_name_the_resource():
    client = Mock()
    client.list_tags_for_resource.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "ListTagsForResource"
    )
    with pytest.raises(ModuleFail) as raised:
        get_resource_tags(client, FakeModule({}), RESOURCE, "IP set")

    assert raised.value.values["msg"] == "Unable to list tags for AWS WAFv2 IP set main/id-1"


def lookup_params(**overrides):
    values = {"id": None, "name": None, "scope": "regional"}
    values.update(overrides)
    return values


@pytest.mark.parametrize("option", ["id", "name"])
def test_require_lookup_params_rejects_empty_identifiers(option):
    with pytest.raises(ModuleFail) as raised:
        wafv2.require_lookup_params(FakeModule(lookup_params(**{option: ""})))

    assert raised.value.values["msg"] == f"{option} must not be empty"


def test_require_lookup_params_requires_us_east_1_for_cloudfront():
    with pytest.raises(ModuleFail) as raised:
        wafv2.require_lookup_params(FakeModule(lookup_params(scope="cloudfront"), region="us-west-2"))

    assert raised.value.values["msg"] == "scope cloudfront requires the us-east-1 region, not us-west-2"


def test_require_lookup_params_accepts_valid_params():
    assert wafv2.require_lookup_params(FakeModule(lookup_params(id="id-1", scope="cloudfront"))) is None


def test_list_resource_summaries_with_id_and_name_skips_the_listing():
    module = FakeModule(lookup_params(id="id-1", name="main"))
    with patch.object(wafv2, "query_list") as query_list:
        summaries = wafv2.list_resource_summaries(Mock(), module, "list_ip_sets", "IPSets", "IP sets", "REGIONAL")

    assert summaries == [{"Id": "id-1", "Name": "main"}]
    query_list.assert_not_called()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, [{"Id": "id-1", "Name": "main"}, {"Id": "id-2", "Name": "other"}]),
        ({"id": "id-2"}, [{"Id": "id-2", "Name": "other"}]),
        ({"name": "main"}, [{"Id": "id-1", "Name": "main"}]),
        ({"name": "missing"}, []),
    ],
)
def test_list_resource_summaries_filters_by_id_or_name(overrides, expected):
    response = [{"Id": "id-1", "Name": "main"}, {"Id": "id-2", "Name": "other"}]
    client = Mock()
    module = FakeModule(lookup_params(**overrides))
    with patch.object(wafv2, "query_list", return_value=response) as query_list:
        summaries = wafv2.list_resource_summaries(client, module, "list_web_acls", "WebACLs", "web ACLs", "REGIONAL")

    assert summaries == expected
    query_list.assert_called_once_with(
        module,
        client,
        "list_web_acls",
        "WebACLs",
        "Unable to list AWS WAFv2 web ACLs for REGIONAL",
        Scope="REGIONAL",
        Limit=100,
    )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (None, "Unexpected response while listing AWS WAFv2 IP sets for REGIONAL"),
        ([None], "Unexpected response while listing AWS WAFv2 IP sets for REGIONAL; invalid ID"),
        ([{"Id": "id-1"}], "Unexpected response while listing AWS WAFv2 IP sets for REGIONAL; invalid name"),
    ],
)
def test_list_resource_summaries_rejects_malformed_responses(response, message):
    module = FakeModule(lookup_params())
    with patch.object(wafv2, "query_list", return_value=response), pytest.raises(ModuleFail) as raised:
        wafv2.list_resource_summaries(Mock(), module, "list_ip_sets", "IPSets", "IP sets", "REGIONAL")

    assert raised.value.values["msg"] == message
