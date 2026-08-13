from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import service_quota_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class ServiceQuotaInfoTests(TestCase):
    def test_missing_adjusted_and_default_quota_returns_empty(self):
        missing = plugin.ClientError(
            {"Error": {"Code": "NoSuchResourceException", "Message": "gone"}},
            "GetServiceQuota",
        )
        client = Mock()
        client.get_service_quota.side_effect = missing
        client.get_aws_default_service_quota.side_effect = missing
        module = FakeModule(
            {"context_id": None, "quota_code": "L-1", "service_code": "ec2"},
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["quota"], {})

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["quota_code"]["required"] is True

    def test_context_id_is_forwarded_to_service_quotas(self):
        client = Mock(get_service_quota=Mock(return_value={"Quota": {"Value": 5.0}}))
        module = FakeModule(
            {"context_id": "arn:context", "quota_code": "L-1", "service_code": "ec2"},
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(client.get_service_quota.call_args.kwargs["ContextId"], "arn:context")
