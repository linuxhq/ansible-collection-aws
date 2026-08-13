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
            patch.object(plugin, "require_client_methods"),
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
