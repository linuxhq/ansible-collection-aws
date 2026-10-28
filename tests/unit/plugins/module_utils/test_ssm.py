from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    association_overview,
    describe_ssm_document,
    list_ssm_tags,
    require_non_null_ssm_filter_values,
    require_valid_ssm_targets,
    ssm_filter_list,
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


def test_ssm_filter_list_groups_string_values_per_filter():
    assert ssm_filter_list({"Owner": "Self", "PlatformTypes": ["Linux", 1]}) == [
        {"Key": "Owner", "Values": ["Self"]},
        {"Key": "PlatformTypes", "Values": ["Linux", "1"]},
    ]


def test_ssm_filter_list_splits_values_with_custom_key_names():
    assert ssm_filter_list({"Name": ["a", "b"], "Status": "Success"}, "key", "value", split_values=True) == [
        {"key": "Name", "value": "a"},
        {"key": "Name", "value": "b"},
        {"key": "Status", "value": "Success"},
    ]


@pytest.mark.parametrize("filters", [{"Owner": "Self", "tag:Env": None}, {"Owner": "Self", "tag:Env": ["a", None]}])
def test_require_non_null_ssm_filter_values_rejects_null_values(filters):
    with pytest.raises(ModuleFail) as raised:
        require_non_null_ssm_filter_values(FakeModule({}), filters)

    assert raised.value.values["msg"] == "filters.tag:Env must not contain a null value"


def test_require_non_null_ssm_filter_values_accepts_scalar_and_list_values():
    require_non_null_ssm_filter_values(FakeModule({}), {"Owner": "Self", "PlatformTypes": ["Linux", 1], "Flag": False})


def test_describe_ssm_document_returns_the_description():
    description = {"DocumentFormat": "TEXT", "Name": "example", "Status": "Active"}
    client = Mock(describe_document=Mock(return_value={"Document": description}))

    assert describe_ssm_document(FakeModule({}), client, "example", DocumentVersion="$LATEST") == description
    client.describe_document.assert_called_once_with(DocumentVersion="$LATEST", Name="example", aws_retry=True)


@pytest.mark.parametrize("code", ["InvalidDocument", "InvalidDocumentVersion"])
def test_describe_ssm_document_returns_none_when_missing(code):
    client = Mock(describe_document=Mock(side_effect=ClientError({"Error": {"Code": code, "Message": "gone"}}, "X")))

    assert describe_ssm_document(FakeModule({}), client, "example") is None


@pytest.mark.parametrize("response", [None, {}, {"Document": {}}, {"Document": {"DocumentFormat": ""}}])
def test_describe_ssm_document_rejects_malformed_responses(response):
    client = Mock(describe_document=Mock(return_value=response))
    with pytest.raises(ModuleFail) as raised:
        describe_ssm_document(FakeModule({}), client, "example")

    assert raised.value.values["msg"] == "Unexpected response while describing AWS Systems Manager document example"


def test_describe_ssm_document_reports_other_errors():
    client = Mock(
        describe_document=Mock(side_effect=ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "X"))
    )
    with pytest.raises(ModuleFail) as raised:
        describe_ssm_document(FakeModule({}), client, "example")

    assert raised.value.values["msg"] == "Unable to describe AWS Systems Manager document example"


def test_require_valid_ssm_targets_accepts_valid_targets():
    require_valid_ssm_targets(FakeModule({}), [{"key": "tag:Role", "values": ["web"] + ["web"] * 50}])
    require_valid_ssm_targets(FakeModule({}), [{"key": "k" * 163, "values": ["web"]}])


@pytest.mark.parametrize(
    ("target", "msg"),
    [
        ({"key": None, "values": ["web"]}, "targets[].key must be 1 to 163 characters"),
        ({"key": "", "values": ["web"]}, "targets[].key must be 1 to 163 characters"),
        # AWS refuses a blank target key with InvalidTarget.
        ({"key": " ", "values": ["web"]}, "targets[].key must be 1 to 163 characters"),
        ({"key": "k" * 164, "values": ["web"]}, "targets[].key must be 1 to 163 characters"),
        ({"key": "tag:Role", "values": []}, "targets[].values must contain at least one entry"),
        (
            {"key": "tag:Role", "values": [str(i) for i in range(51)]},
            "targets[].values must contain at most 50 entries",
        ),
    ],
)
def test_require_valid_ssm_targets_rejects_invalid_targets(target, msg):
    with pytest.raises(ModuleFail) as raised:
        require_valid_ssm_targets(FakeModule({}), [target])

    assert raised.value.values == {"msg": msg}
