from unittest import TestCase
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.modules import sns_topic_attributes as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class SnsTopicAttributesTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["topic_arn"]["required"] is True

    def test_check_mode_does_not_set_changed_attribute(self):
        client = Mock(get_topic_attributes=Mock(return_value={"Attributes": {"KmsMasterKeyId": "old"}}))
        module = FakeModule(
            {"kms_master_key_id": "new", "topic_arn": "arn:topic"},
            check_mode=True,
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        client.set_topic_attributes.assert_not_called()
        self.assertTrue(raised.exception.values["changed"])

    def test_missing_topic_fails_in_check_mode(self):
        error = ClientError(
            {"Error": {"Code": "NotFound", "Message": "missing"}},
            "GetTopicAttributes",
        )
        client = Mock(get_topic_attributes=Mock(side_effect=error))
        module = FakeModule(
            {"kms_master_key_id": "new", "topic_arn": "arn:missing"},
            check_mode=True,
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()

        self.assertIn("does not exist", raised.exception.values["msg"])
        client.set_topic_attributes.assert_not_called()

    def test_report_only_mode_does_not_require_set_method(self):
        client = Mock(get_topic_attributes=Mock(return_value={"Attributes": {}}))
        module = FakeModule({"kms_master_key_id": None, "topic_arn": "arn:topic"}, client=client)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_methods.assert_called_once_with(module, client, "SNS", {"get_topic_attributes": ("TopicArn",)})
        client.set_topic_attributes.assert_not_called()
