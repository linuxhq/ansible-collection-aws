from unittest import TestCase
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import service_quota_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
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
        client = Mock(
            get_service_quota=Mock(return_value={"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "arn:context"}}})
        )
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

    def test_quota_from_response_rejects_invalid_response(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.quota_from_response(module, [], "service quota", "ec2", "L-1")

        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Service Quotas returned an invalid service quota response",
        )

    def test_quota_from_response_rejects_mismatched_quota(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.quota_from_response(
                module,
                {"Quota": {"ServiceCode": "iam", "QuotaCode": "L-1"}},
                "service quota",
                "ec2",
                "L-1",
            )

        self.assertIn("mismatched quota", raised.exception.values["msg"])

    def test_quota_from_response_rejects_mismatched_context(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.quota_from_response(
                module,
                {"Quota": {"Value": 5.0, "QuotaContext": {"ContextId": "wrong"}}},
                "service quota",
                "ec2",
                "L-1",
                "expected",
            )

        self.assertIn("mismatched quota context", raised.exception.values["msg"])

    def test_quota_from_response_rejects_invalid_context(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.quota_from_response(
                module,
                {"Quota": {"Value": 5.0, "QuotaContext": "invalid"}},
                "service quota",
                "ec2",
                "L-1",
            )

        self.assertIn("invalid quota context", raised.exception.values["msg"])


def test_metric_dimension_identifiers_are_preserved():
    dimensions = {"Class": "Standard/OnDemand", "class": "distinct", "Resource": "vCPU", "Service": "EC2"}
    current = {
        "QuotaCode": "L-example",
        "ServiceCode": "ec2",
        "Value": 10.0,
        "UsageMetric": {"MetricNamespace": "AWS/Usage", "MetricName": "ResourceCount", "MetricDimensions": dimensions},
    }
    client = Mock(get_service_quota=Mock(return_value={"Quota": current}))
    module = FakeModule(
        {"quota_code": "L-example", "service_code": "ec2", "value": 10.0, "context_id": None}, client=client
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    metric = result.value.values["quota"]["usage_metric"]
    assert metric == {"metric_namespace": "AWS/Usage", "metric_name": "ResourceCount", "metric_dimensions": dimensions}
