# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import list_contact_tags
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)

MISSING = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}}, "ListTagsForResource")
# Live: ListTagsForResource on a deleted contact's well-formed ARN.
NOT_FOUND = ClientError(
    {"Error": {"Code": "NotFoundException", "Message": "Resource was not found"}}, "ListTagsForResource"
)
DENIED = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "ListTagsForResource")


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({}, {}),
        ({"tags": {}}, {}),
        ({"tags": {"Name": "ops"}}, {"Name": "ops"}),
    ],
)
def test_list_contact_tags_returns_listed_tags(response, expected):
    client = Mock(list_tags_for_resource=Mock(return_value=response))

    assert list_contact_tags(client, FakeModule({}), "arn:contact") == expected


@pytest.mark.parametrize("missing_ok", [False, True])
def test_list_contact_tags_returns_the_tag_dictionary(missing_ok):
    client = Mock(list_tags_for_resource=Mock(return_value={"tags": {"Name": "ops"}}))

    assert list_contact_tags(client, FakeModule({}), "arn:contact", missing_ok=missing_ok) == {"Name": "ops"}
    client.list_tags_for_resource.assert_called_once_with(arn="arn:contact", aws_retry=True)


@pytest.mark.parametrize("error", [MISSING, NOT_FOUND], ids=["resource-not-found", "not-found"])
def test_list_contact_tags_returns_none_for_a_missing_contact_when_allowed(error):
    client = Mock(list_tags_for_resource=Mock(side_effect=error))

    assert list_contact_tags(client, FakeModule({}), "arn:contact", missing_ok=True) is None


@pytest.mark.parametrize(
    ("error", "missing_ok"),
    [(MISSING, False), (NOT_FOUND, False), (DENIED, False), (DENIED, True)],
)
def test_list_contact_tags_reports_errors(error, missing_ok):
    client = Mock(list_tags_for_resource=Mock(side_effect=error))
    with pytest.raises(ModuleFail) as raised:
        list_contact_tags(client, FakeModule({}), "arn:contact", missing_ok=missing_ok)

    assert raised.value.values == {"msg": "Unable to list tags for AWS Notifications contact arn:contact"}
