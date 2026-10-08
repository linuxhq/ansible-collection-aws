# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import contact_tags
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({}, {}),
        ({"tags": {}}, {}),
        ({"tags": {"Name": "ops"}}, {"Name": "ops"}),
    ],
)
def test_contact_tags_returns_listed_tags(response, expected):
    assert contact_tags(FakeModule({}), response, "arn:contact") == expected


@pytest.mark.parametrize(
    "response",
    [None, {"tags": None}, {"tags": []}, {"tags": {"Name": 1}}, {"tags": {1: "ops"}}],
)
def test_contact_tags_rejects_invalid_responses(response):
    with pytest.raises(ModuleFail) as raised:
        contact_tags(FakeModule({}), response, "arn:contact")

    assert raised.value.values == {
        "msg": "Unable to list tags for AWS Notifications contact arn:contact: AWS returned an invalid response"
    }
