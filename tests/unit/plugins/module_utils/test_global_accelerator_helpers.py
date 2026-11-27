# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import global_accelerator as global_accelerator_utils
from ansible_collections.linuxhq.aws.plugins.module_utils.global_accelerator import (
    get_accelerator_by_arn,
    list_accelerator_tags,
    list_accelerators,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)

ARN = "arn:aws:globalaccelerator::123456789012:accelerator/example"
MISSING = ClientError({"Error": {"Code": "AcceleratorNotFoundException", "Message": "gone"}}, "ListTagsForResource")
DENIED = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "ListTagsForResource")


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


def test_list_accelerator_tags_defaults_to_no_tags():
    client = Mock(list_tags_for_resource=Mock(return_value={}))

    assert list_accelerator_tags(client, FakeModule({}), ARN) == []


def test_list_accelerators_checks_the_sdk_and_lists_every_accelerator():
    accelerators = [{"AcceleratorArn": ARN, "Name": "example"}]
    client = Mock()
    module = FakeModule({})
    with (
        patch.object(global_accelerator_utils, "require_client_methods") as require,
        patch.object(global_accelerator_utils, "query_list", return_value=accelerators) as query_list,
    ):
        assert list_accelerators(client, module) == accelerators

    require.assert_called_once_with(
        module, client, "Global Accelerator", {"list_accelerators": ("MaxResults", "NextToken")}
    )
    query_list.assert_called_once_with(
        module, client, "list_accelerators", "Accelerators", "Unable to list AWS Global Accelerator accelerators"
    )


def test_get_accelerator_by_arn_returns_the_described_accelerator():
    accelerator = {"AcceleratorArn": ARN, "Name": "example"}
    client = Mock(describe_accelerator=Mock(return_value={"Accelerator": accelerator}))
    with patch.object(global_accelerator_utils, "require_client_methods") as require:
        assert get_accelerator_by_arn(client, FakeModule({}), ARN) == accelerator

    assert require.call_args.args[3] == {"describe_accelerator": ("AcceleratorArn",)}
    client.describe_accelerator.assert_called_once_with(AcceleratorArn=ARN, aws_retry=True)


def test_get_accelerator_by_arn_returns_none_for_a_missing_accelerator():
    missing = ClientError({"Error": {"Code": "AcceleratorNotFoundException", "Message": "gone"}}, "DescribeAccelerator")
    client = Mock(describe_accelerator=Mock(side_effect=missing))
    with patch.object(global_accelerator_utils, "require_client_methods"):
        assert get_accelerator_by_arn(client, FakeModule({}), ARN) is None
