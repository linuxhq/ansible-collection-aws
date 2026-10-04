from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

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
