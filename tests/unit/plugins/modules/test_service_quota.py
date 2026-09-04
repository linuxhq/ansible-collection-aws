from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import service_quota as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class ServiceQuotaTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["value"]["type"] == "float"

    def test_rejects_negative_quota_value(self):
        module = FakeModule({"quota_code": "L-1", "service_code": "ec2", "value": -1})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("between 0", raised.exception.values["msg"])

    def test_rejects_non_finite_quota_value(self):
        for value in (float("inf"), float("nan")):
            with self.subTest(value=value):
                module = FakeModule({"quota_code": "L-1", "service_code": "ec2", "value": value})
                with (
                    patch.object(plugin, "AnsibleAWSModule", return_value=module),
                    self.assertRaises(ModuleFail) as raised,
                ):
                    plugin.main()
                self.assertIn("between 0", raised.exception.values["msg"])

    def test_response_resource_rejects_invalid_response(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.response_resource(module, [], "Quota", "service quota")
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Service Quotas returned an invalid service quota response",
        )

    def test_response_resources_rejects_invalid_entry(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.response_resources(module, {"RequestedQuotas": [None]}, "RequestedQuotas", "quota history")
        self.assertEqual(
            raised.exception.values["msg"],
            "AWS Service Quotas returned an invalid quota history entry",
        )

    def test_validate_current_quota_rejects_mismatched_quota(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.validate_current_quota(
                module,
                {"ServiceCode": "iam", "QuotaCode": "L-1", "Value": 5.0},
                "ec2",
                "L-1",
            )
        self.assertIn("mismatched quota", raised.exception.values["msg"])

    def test_validate_current_quota_rejects_invalid_value(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.validate_current_quota(module, {"Value": "5"}, "ec2", "L-1")
        self.assertIn("valid value", raised.exception.values["msg"])

    def test_validate_current_quota_accepts_large_integer_without_crashing(self):
        module = FakeModule({})
        plugin.validate_current_quota(module, {"Value": 10**400}, "ec2", "L-1")

    def test_validate_quota_request_rejects_empty_request(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.validate_quota_request(module, {}, "ec2", "L-1")
        self.assertIn("invalid request", raised.exception.values["msg"])

    def test_validate_quota_request_rejects_wrong_status(self):
        module = FakeModule({})
        with self.assertRaises(ModuleFail) as raised:
            plugin.validate_quota_request(module, {"Status": "PENDING"}, "ec2", "L-1", status="CASE_OPENED")
        self.assertIn("mismatched request", raised.exception.values["msg"])

    def test_check_mode_reports_the_quota_request(self):
        client = Mock()
        client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
        module = FakeModule(
            {"quota_code": "L-1", "service_code": "ec2", "value": 10.0},
            check_mode=True,
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_client_methods,
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"RequestedQuotas": []},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["requested_quota"]["desired_value"], 10.0)
        client.request_service_quota_increase.assert_not_called()
        self.assertNotIn("request_service_quota_increase", require_client_methods.call_args.args[3])

    def test_pending_request_prevents_a_duplicate_request(self):
        client = Mock()
        client.get_service_quota.return_value = {"Quota": {"Value": 5.0}}
        module = FakeModule(
            {"quota_code": "L-1", "service_code": "ec2", "value": 10.0},
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "paginated_query_with_retries",
                side_effect=[{"RequestedQuotas": [{"Status": "CASE_OPENED"}]}, {}],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertFalse(raised.exception.values["changed"])
        client.request_service_quota_increase.assert_not_called()
