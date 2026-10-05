from pathlib import Path
from unittest.mock import Mock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.session import get_session
from botocore.stub import Stubber

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.linuxhq.aws.plugins.modules import sqs_queue_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    HEADER,
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    documented_returns,
)

NOT_FOUND_CODES = ("AWS.SimpleQueueService.NonExistentQueue", "QueueDoesNotExist")


def params(**overrides):
    values = {"name": None, "queue_name_prefix": None, "queue_owner_aws_account_id": None}
    values.update(overrides)
    return values


def missing(code, operation):
    return ClientError({"Error": {"Code": code, "Message": "missing"}}, operation)


def queue_client(attributes=None, tags=None):
    return Mock(
        get_queue_attributes=Mock(return_value={"Attributes": attributes or {}}),
        list_queue_tags=Mock(return_value={"Tags": tags} if tags is not None else {}),
    )


def run(module):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods


def test_module_contract():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert captured["required_by"] == {"queue_owner_aws_account_id": ["name"]}
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER


def test_queue_name_is_derived_from_arn():
    client = queue_client({"QueueArn": "arn:aws:sqs:us-east-1:1:main"})
    queue = plugin.get_queue(client, Mock(), "https://sqs.example/other")

    assert queue["name"] == "main"
    assert queue["queue_url"] == "https://sqs.example/other"


def test_tags_are_returned_with_their_case():
    client = queue_client({"QueueArn": "arn:aws:sqs:us-east-1:1:main"}, {"Name": "main", "CostCenter": "A1"})
    queue = plugin.get_queue(client, FakeModule({}), "https://sqs/main")

    assert queue["tags"] == {"Name": "main", "CostCenter": "A1"}
    client.list_queue_tags.assert_called_once_with(QueueUrl="https://sqs/main", aws_retry=True)


def test_untagged_queue_returns_empty_tags():
    queue = plugin.get_queue(
        queue_client({"QueueArn": "arn:aws:sqs:us-east-1:1:main"}), FakeModule({}), "https://sqs/main"
    )

    assert queue["tags"] == {}


def test_empty_name_is_rejected():
    result, _require = run(FakeModule(params(name="")))

    assert result.values["msg"] == "name must not be empty"


@pytest.mark.parametrize("code", NOT_FOUND_CODES)
def test_get_queue_skips_a_missing_queue(code):
    client = queue_client()
    client.get_queue_attributes.side_effect = missing(code, "GetQueueAttributes")

    assert plugin.get_queue(client, FakeModule({}), "https://sqs/queue") is None


@pytest.mark.parametrize("code", NOT_FOUND_CODES)
def test_get_queue_skips_a_queue_deleted_before_its_tags_are_read(code):
    client = queue_client()
    client.list_queue_tags.side_effect = missing(code, "ListQueueTags")

    assert plugin.get_queue(client, FakeModule({}), "https://sqs/queue") is None


@pytest.mark.parametrize(
    ("client", "message"),
    [
        (
            Mock(get_queue_attributes=Mock(return_value={"Attributes": []})),
            "Unexpected response while getting AWS SQS queue https://sqs/queue",
        ),
        (
            Mock(
                get_queue_attributes=Mock(return_value={"Attributes": {}}),
                list_queue_tags=Mock(return_value={"Tags": []}),
            ),
            "Unexpected response while listing AWS SQS queue tags for https://sqs/queue",
        ),
    ],
)
def test_get_queue_rejects_malformed_responses(client, message):
    with pytest.raises(ModuleFail) as raised:
        plugin.get_queue(client, FakeModule({}), "https://sqs/queue")

    assert raised.value.values["msg"] == message


def test_get_queue_url_accepts_modeled_not_found_error():
    client = Mock()
    client.get_queue_url.side_effect = missing("QueueDoesNotExist", "GetQueueUrl")
    module = FakeModule(params(name="missing"), client=client)
    result, require_client_methods = run(module)

    assert result.values["queues"] == []
    require_client_methods.assert_called_once_with(
        module,
        client,
        "SQS",
        {
            "get_queue_attributes": ("AttributeNames", "QueueUrl"),
            "list_queue_tags": ("QueueUrl",),
            "get_queue_url": ("QueueName",),
        },
    )


def test_get_queue_url_rejects_malformed_response():
    client = Mock(get_queue_url=Mock(return_value={"QueueUrl": None}))
    result, _require = run(FakeModule(params(name="main"), client=client))

    assert result.values["msg"] == "Unexpected response while getting AWS SQS queue URL for main"


def test_sqs_pagination_supplies_page_size():
    client = boto3.client("sqs", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test")
    module = FakeModule(params(), client=client)
    with Stubber(client) as stubber:
        queue_urls = [f"https://sqs.us-east-1.amazonaws.com/123456789012/queue-{index}" for index in range(1001)]
        stubber.add_response(
            "list_queues", {"QueueUrls": queue_urls[:1000], "NextToken": "page-2"}, {"MaxResults": 1000}
        )
        stubber.add_response(
            "list_queues", {"QueueUrls": queue_urls[1000:]}, {"MaxResults": 1000, "NextToken": "page-2"}
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "get_queue", side_effect=lambda client, module, url: {"queue_url": url}),
            pytest.raises(ModuleExit) as result,
        ):
            plugin.main()

        stubber.assert_no_pending_responses()

    assert [queue["queue_url"] for queue in result.value.values["queues"]] == queue_urls


def test_return_documents_every_queue_attribute():
    names = get_session().get_service_model("sqs").shape_for("QueueAttributeName").enum
    expected = set(camel_dict_to_snake_dict(dict.fromkeys(name for name in names if name != "All")))
    contains = documented_returns(plugin)["queues"]["contains"]

    assert expected <= set(contains), sorted(expected - set(contains))
    assert all(contains[name]["type"] == "str" for name in expected)
