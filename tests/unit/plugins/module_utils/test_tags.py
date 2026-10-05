# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    reconcile_ec2_tags,
    reconcile_ssm_tags,
    require_valid_tag_list,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


def test_tag_limits_are_rejected():
    module = FakeModule({})
    for tags, message in (
        ({"one": "", "two": ""}, "tags must contain at most 1 entries"),
        ({"long": "v" * 257}, "tag keys must contain 1 to 3 characters and values at most 256 characters"),
    ):
        with pytest.raises(ModuleFail) as raised:
            require_valid_tags(module, tags, 1, key_max=3)

        assert raised.value.values["msg"] == message


def test_tag_keys_and_values_are_normalized_for_map_apis():
    tags = {1: True, "count": 2}
    require_valid_tags(FakeModule({}), tags, 50)
    assert tags == {"1": "True", "count": "2"}


def test_colliding_normalized_tag_keys_are_rejected():
    with pytest.raises(ModuleFail) as raised:
        require_valid_tags(FakeModule({}), {1: "numeric", "1": "string"}, 50)

    assert raised.value.values["msg"] == "tag keys must be unique after string normalization"


def test_tag_deltas_do_not_mutate_source():
    resource = {"Arn": "arn:resource", "Tags": [{"Key": "old", "Value": "value"}]}
    updated = apply_tag_deltas(resource, {"new": "value"}, ["old"])
    assert updated["Tags"] == [{"Key": "new", "Value": "value"}]
    assert resource["Tags"] == [{"Key": "old", "Value": "value"}]


def test_reconcile_arn_tags_only_calls_nonempty_operations():
    client = Mock()
    reconcile_arn_tags(Mock(), client, "arn:resource", {"new": "value"}, [], "resource")
    client.untag_resource.assert_not_called()
    client.tag_resource.assert_called_once_with(
        ResourceArn="arn:resource", Tags=[{"Key": "new", "Value": "value"}], aws_retry=True
    )


def test_reconcile_ssm_tags_uses_ssm_parameter_names():
    client = Mock()
    reconcile_ssm_tags(Mock(), client, "Document", "doc", {}, ["old"], "document")
    client.add_tags_to_resource.assert_not_called()
    client.remove_tags_from_resource.assert_called_once_with(
        ResourceType="Document", ResourceId="doc", TagKeys=["old"], aws_retry=True
    )


def test_reconcile_ec2_tags_removes_then_adds_tags():
    client = Mock()
    reconcile_ec2_tags(Mock(), client, ["fl-1", "fl-2"], {"new": "value"}, ("old",), "EC2 flow logs")
    client.delete_tags.assert_called_once_with(Resources=["fl-1", "fl-2"], Tags=[{"Key": "old"}], aws_retry=True)
    client.create_tags.assert_called_once_with(
        Resources=["fl-1", "fl-2"], Tags=[{"Key": "new", "Value": "value"}], aws_retry=True
    )
    assert [call[0] for call in client.method_calls] == ["delete_tags", "create_tags"]


@pytest.mark.parametrize(
    ("tags_to_set", "tag_keys_to_unset", "called", "not_called"),
    (
        ({"new": "value"}, [], "create_tags", "delete_tags"),
        ({}, ["old"], "delete_tags", "create_tags"),
    ),
)
def test_reconcile_ec2_tags_only_calls_nonempty_operations(tags_to_set, tag_keys_to_unset, called, not_called):
    client = Mock()
    reconcile_ec2_tags(Mock(), client, ["rtb-1"], tags_to_set, tag_keys_to_unset, "resource")
    getattr(client, called).assert_called_once()
    getattr(client, not_called).assert_not_called()


@pytest.mark.parametrize(
    ("method", "tags_to_set", "tag_keys_to_unset", "message"),
    (
        ("delete_tags", {}, ["old"], "Unable to remove tags from EC2 flow logs fl-1, fl-2"),
        ("create_tags", {"new": "value"}, [], "Unable to tag EC2 flow logs fl-1, fl-2"),
    ),
)
def test_reconcile_ec2_tags_failures_name_resources(method, tags_to_set, tag_keys_to_unset, message):
    client = Mock()
    getattr(client, method).side_effect = ClientError({"Error": {"Code": "Failed", "Message": "no"}}, method)
    with pytest.raises(ModuleFail) as raised:
        reconcile_ec2_tags(FakeModule({}), client, ["fl-1", "fl-2"], tags_to_set, tag_keys_to_unset, "EC2 flow logs")

    assert raised.value.values["msg"] == message


def test_valid_tag_list_is_returned_unchanged():
    tags = [{"Key": "Name", "Value": "example"}, {"Key": "Empty", "Value": ""}]

    assert require_valid_tag_list(FakeModule({}), tags, "invalid tags") is tags
    assert require_valid_tag_list(FakeModule({}), [], "invalid tags") == []


@pytest.mark.parametrize(
    "tags",
    [
        None,
        {"Key": "Name", "Value": "example"},
        ["Name"],
        [{"Key": "Name"}],
        [{"Value": "example"}],
        [{"Key": 1, "Value": "example"}],
        [{"Key": "Name", "Value": None}],
    ],
)
def test_invalid_tag_list_fails_with_caller_message(tags):
    with pytest.raises(ModuleFail) as raised:
        require_valid_tag_list(FakeModule({}), tags, "invalid tags")

    assert raised.value.values["msg"] == "invalid tags"


def test_reconcile_ssm_tags_reports_changed_after_removing_tags():
    client = Mock()
    client.add_tags_to_resource.side_effect = ClientError({"Error": {"Code": "Throttling", "Message": "no"}}, "Tag")
    with pytest.raises(ModuleFail) as raised:
        reconcile_ssm_tags(FakeModule({}), client, "Document", "doc", {"new": "value"}, ["old"], "document")

    assert raised.value.values["changed"] is True


@pytest.mark.parametrize("changed", [False, True])
def test_reconcile_ssm_tags_reports_the_supplied_changed_state(changed):
    client = Mock()
    client.remove_tags_from_resource.side_effect = ClientError(
        {"Error": {"Code": "Throttling", "Message": "no"}}, "Untag"
    )
    with pytest.raises(ModuleFail) as raised:
        reconcile_ssm_tags(FakeModule({}), client, "Document", "doc", {}, ["old"], "document", changed=changed)

    assert raised.value.values["changed"] is changed
