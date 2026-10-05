from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    association_overview,
    list_ssm_tags,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import FakeModule, ModuleFail

MISSING = ClientError({"Error": {"Code": "InvalidResourceId", "Message": "gone"}}, "ListTagsForResource")


def test_association_overview_preserves_status_names():
    overview = {"AssociationStatusAggregatedCount": {"InProgress": 1}, "DetailedStatus": "Success"}

    assert association_overview(overview) == {
        "association_status_aggregated_count": {"InProgress": 1},
        "detailed_status": "Success",
    }


def test_association_overview_preserves_status_names_under_another_key():
    overview = {"InstanceAssociationStatusAggregatedCount": {"Success": 2}, "DetailedStatus": "Success"}

    assert association_overview(overview, "InstanceAssociationStatusAggregatedCount") == {
        "instance_association_status_aggregated_count": {"Success": 2},
        "detailed_status": "Success",
    }


def test_association_overview_passes_through_non_dict():
    assert association_overview(None) is None


def test_list_ssm_tags_returns_the_tag_list():
    tags = [{"Key": "CostCenter", "Value": "A1"}]
    client = Mock(list_tags_for_resource=Mock(return_value={"TagList": tags}))

    assert list_ssm_tags(FakeModule({}), client, "Document", "example", "AWS Systems Manager document") == tags
    client.list_tags_for_resource.assert_called_once_with(ResourceType="Document", ResourceId="example", aws_retry=True)


def test_list_ssm_tags_returns_none_for_a_missing_resource_when_allowed():
    client = Mock(list_tags_for_resource=Mock(side_effect=MISSING))

    assert (
        list_ssm_tags(FakeModule({}), client, "Association", "a-1", "AWS Systems Manager association", missing_ok=True)
        is None
    )


@pytest.mark.parametrize("changed", [False, True])
def test_list_ssm_tags_fails_for_a_missing_resource_by_default(changed):
    client = Mock(list_tags_for_resource=Mock(side_effect=MISSING))
    with pytest.raises(ModuleFail) as raised:
        list_ssm_tags(FakeModule({}), client, "Document", "example", "AWS Systems Manager document", changed=changed)

    assert raised.value.values == {
        "changed": changed,
        "msg": "Unable to list tags for AWS Systems Manager document example",
    }


@pytest.mark.parametrize("response", [None, {"TagList": None}, {"TagList": [None]}])
def test_list_ssm_tags_rejects_malformed_responses(response):
    client = Mock(list_tags_for_resource=Mock(return_value=response))
    with pytest.raises(ModuleFail) as raised:
        list_ssm_tags(FakeModule({}), client, "Association", "a-1", "AWS Systems Manager association")

    assert (
        raised.value.values["msg"] == "Unexpected response while listing tags for AWS Systems Manager association a-1"
    )
