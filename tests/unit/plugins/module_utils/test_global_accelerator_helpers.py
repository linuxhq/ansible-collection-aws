# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.global_accelerator import (
    list_accelerator_tags,
    validate_tag_list,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)

ARN = "arn:aws:globalaccelerator::123456789012:accelerator/example"
MISSING = ClientError({"Error": {"Code": "AcceleratorNotFoundException", "Message": "gone"}}, "ListTagsForResource")
DENIED = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "ListTagsForResource")


@pytest.mark.parametrize(
    "tags",
    [None, [None], [{"Key": "Name"}], [{"Key": 1, "Value": "value"}], [{"Key": "", "Value": "value"}]],
)
def test_invalid_tag_lists_are_rejected(tags):
    with pytest.raises(ModuleFail) as raised:
        validate_tag_list(FakeModule({}), tags)

    assert raised.value.values["msg"] == "Global Accelerator returned invalid tags"
    assert not raised.value.values.get("changed")


def test_valid_tag_lists_are_returned():
    tags = [{"Key": "Name", "Value": ""}]
    assert validate_tag_list(FakeModule({}), tags) is tags


@pytest.mark.parametrize("missing_ok", [False, True])
def test_list_accelerator_tags_returns_the_tag_list(missing_ok):
    tags = [{"Key": "Name", "Value": "example"}]
    client = Mock(list_tags_for_resource=Mock(return_value={"Tags": tags}))

    assert list_accelerator_tags(client, FakeModule({}), ARN, missing_ok=missing_ok) == tags
    client.list_tags_for_resource.assert_called_once_with(ResourceArn=ARN, aws_retry=True)


def test_list_accelerator_tags_returns_none_for_a_missing_accelerator_when_allowed():
    client = Mock(list_tags_for_resource=Mock(side_effect=MISSING))

    assert list_accelerator_tags(client, FakeModule({}), ARN, missing_ok=True) is None


@pytest.mark.parametrize(
    ("error", "missing_ok"),
    [(MISSING, False), (DENIED, False), (DENIED, True)],
)
def test_list_accelerator_tags_reports_errors(error, missing_ok):
    client = Mock(list_tags_for_resource=Mock(side_effect=error))
    with pytest.raises(ModuleFail) as raised:
        list_accelerator_tags(client, FakeModule({}), ARN, missing_ok=missing_ok)

    assert raised.value.values == {"msg": f"Unable to list tags for AWS Global Accelerator {ARN}"}


@pytest.mark.parametrize("response", [None, {}, {"Tags": [{"Key": "", "Value": "value"}]}])
def test_list_accelerator_tags_rejects_malformed_responses(response):
    client = Mock(list_tags_for_resource=Mock(return_value=response))
    with pytest.raises(ModuleFail) as raised:
        list_accelerator_tags(client, FakeModule({}), ARN)

    assert raised.value.values["msg"] == "Global Accelerator returned invalid tags"
    assert not raised.value.values.get("changed")
