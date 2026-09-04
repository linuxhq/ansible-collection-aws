from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import sqs_queue_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class SqsQueueInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_by"] == {"queue_owner_aws_account_id": ["name"]}

    def test_queue_name_is_derived_from_arn(self):
        client = Mock(
            get_queue_attributes=Mock(return_value={"Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:1:main"}})
        )
        queue = plugin.get_queue(client, Mock(), "https://sqs.example/other")
        self.assertEqual(queue["name"], "main")
        self.assertEqual(queue["queue_url"], "https://sqs.example/other")

    def test_empty_name_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "name": "",
                "queue_name_prefix": None,
                "queue_owner_aws_account_id": None,
            },
            "name must not be empty",
        )

    def test_get_queue_accepts_both_not_found_error_codes(self):
        for code in ("AWS.SimpleQueueService.NonExistentQueue", "QueueDoesNotExist"):
            with self.subTest(code=code):
                client = Mock()
                client.get_queue_attributes.side_effect = plugin.ClientError(
                    {"Error": {"Code": code, "Message": "missing"}},
                    "GetQueueAttributes",
                )
                self.assertIsNone(plugin.get_queue(client, FakeModule({}), "https://sqs/queue"))

    def test_get_queue_rejects_malformed_attributes(self):
        client = Mock(get_queue_attributes=Mock(return_value={"Attributes": []}))
        with self.assertRaises(ModuleFail) as raised:
            plugin.get_queue(client, FakeModule({}), "https://sqs/queue")
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS SQS queue https://sqs/queue",
        )

    def test_get_queue_url_accepts_modeled_not_found_error(self):
        client = Mock()
        client.get_queue_url.side_effect = plugin.ClientError(
            {"Error": {"Code": "QueueDoesNotExist", "Message": "missing"}},
            "GetQueueUrl",
        )
        module = FakeModule(
            {
                "name": "missing",
                "queue_name_prefix": None,
                "queue_owner_aws_account_id": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["queues"], [])
        require_methods.assert_called_once_with(
            module,
            client,
            "SQS",
            {
                "get_queue_attributes": ("AttributeNames", "QueueUrl"),
                "get_queue_url": ("QueueName",),
            },
        )

    def test_get_queue_url_rejects_malformed_response(self):
        client = Mock(get_queue_url=Mock(return_value={"QueueUrl": None}))
        module = FakeModule(
            {
                "name": "main",
                "queue_name_prefix": None,
                "queue_owner_aws_account_id": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "Unexpected response while getting AWS SQS queue URL for main",
        )
