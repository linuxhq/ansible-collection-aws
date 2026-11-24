from unittest.mock import Mock, patch

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.session import get_session
from botocore.stub import Stubber

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.linuxhq.aws.plugins.modules import sqs_queue_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    documented_returns,
)

NOT_FOUND_CODES = ("AWS.SimpleQueueService.NonExistentQueue", "QueueDoesNotExist")
CALLER_ACCOUNT = "123456789012"
OTHER_ACCOUNT = "210987654321"


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
    options = assert_module_contract(plugin)
    assert options["required_by"] == {"queue_owner_aws_account_id": ["name"]}


def test_queue_name_is_derived_from_the_url():
    client = queue_client({"QueueArn": "arn:aws:sqs:us-east-1:1:main.fifo"})
    queue = plugin.get_queue(client, Mock(), "https://sqs.us-east-1.amazonaws.com/1/main.fifo")

    assert queue["name"] == "main.fifo"
    assert queue["queue_url"] == "https://sqs.us-east-1.amazonaws.com/1/main.fifo"


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


def service_module(owner, sqs, sts):
    module = FakeModule(params(name="main", queue_owner_aws_account_id=owner))
    module.client = Mock(side_effect=lambda service, **kwargs: {"sqs": sqs, "sts": sts}[service])
    return module


def run_named_queue(owner, identity=None):
    queue_url = f"https://sqs.us-east-1.amazonaws.com/{owner or CALLER_ACCOUNT}/main"
    sqs = queue_client({"QueueArn": f"arn:aws:sqs:us-east-1:{owner or CALLER_ACCOUNT}:main"}, {"Name": "main"})
    sqs.get_queue_url = Mock(return_value={"QueueUrl": queue_url})
    sts = Mock(get_caller_identity=identity or Mock(return_value={"Account": CALLER_ACCOUNT}))
    module = service_module(owner, sqs, sts)
    result, _require = run(module)

    assert [queue["queue_url"] for queue in result.values["queues"]] == [queue_url]
    return result.values["queues"][0], sqs, sts, [call.args[0] for call in module.client.call_args_list]


def test_another_accounts_queue_is_returned_without_tags():
    queue, sqs, sts, services = run_named_queue(OTHER_ACCOUNT)

    assert "tags" not in queue
    assert queue["name"] == "main"
    sqs.get_queue_url.assert_called_once_with(QueueName="main", QueueOwnerAWSAccountId=OTHER_ACCOUNT, aws_retry=True)
    sqs.list_queue_tags.assert_not_called()
    sts.get_caller_identity.assert_called_once_with(aws_retry=True)
    assert services == ["sqs", "sts"]


def test_callers_own_account_as_queue_owner_reads_tags():
    queue, sqs, sts, services = run_named_queue(CALLER_ACCOUNT)

    assert queue["tags"] == {"Name": "main"}
    sqs.list_queue_tags.assert_called_once_with(QueueUrl=queue["queue_url"], aws_retry=True)
    sts.get_caller_identity.assert_called_once_with(aws_retry=True)
    assert services == ["sqs", "sts"]


def test_queue_without_owner_reads_tags_without_looking_up_the_caller():
    queue, sqs, sts, services = run_named_queue(None)

    assert queue["tags"] == {"Name": "main"}
    sqs.get_queue_url.assert_called_once_with(QueueName="main", aws_retry=True)
    sqs.list_queue_tags.assert_called_once_with(QueueUrl=queue["queue_url"], aws_retry=True)
    sts.get_caller_identity.assert_not_called()
    assert services == ["sqs"]


@pytest.mark.parametrize(
    "identity",
    [
        Mock(side_effect=missing("InvalidClientTokenId", "GetCallerIdentity")),
        Mock(side_effect=EndpointConnectionError(endpoint_url="https://vpce-0123.sqs.us-east-1.vpce.amazonaws.com")),
        Mock(return_value={}),
    ],
)
def test_unknown_caller_reads_tags_as_before(identity):
    queue, sqs, _sts, services = run_named_queue(CALLER_ACCOUNT, identity)

    assert queue["tags"] == {"Name": "main"}
    sqs.list_queue_tags.assert_called_once_with(QueueUrl=queue["queue_url"], aws_retry=True)
    identity.assert_called_once_with(aws_retry=True)
    assert services == ["sqs", "sts"]


def test_missing_queue_with_owner_does_not_look_up_the_caller():
    sqs = Mock()
    sqs.get_queue_url.side_effect = missing("QueueDoesNotExist", "GetQueueUrl")
    sts = Mock()
    module = service_module(OTHER_ACCOUNT, sqs, sts)
    result, _require = run(module)

    assert result.values["queues"] == []
    sts.get_caller_identity.assert_not_called()
    assert [call.args[0] for call in module.client.call_args_list] == ["sqs"]


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


def test_empty_name_lists_every_queue():
    client = Mock()
    module = FakeModule(params(name=""), client=client)
    with patch.object(plugin, "query_list", return_value=[]) as query_list:
        result, _require = run(module)

    assert result.values["queues"] == []
    assert query_list.call_args.args[2] == "list_queues"
    assert query_list.call_args.kwargs == {"MaxResults": 1000}
    client.get_queue_url.assert_not_called()
