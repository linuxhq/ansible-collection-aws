from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ec2_pricing_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class Ec2PricingInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["service_code"]["default"] == "AmazonEC2"

    def test_empty_filters_return_without_creating_client(self):
        module = FakeModule(
            {
                "filters": [],
                "format_version": "aws_v1",
                "max_results": None,
                "service_code": "AmazonEC2",
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["products"], [])

    def test_product_terms_preserve_case_sensitive_aws_keys(self):
        client = Mock()
        module = FakeModule(
            {
                "filters": [{"field": "instanceType", "type": "TERM_MATCH", "value": "t3"}],
                "format_version": "aws_v1",
                "max_results": None,
                "service_code": "AmazonEC2",
            },
            client=client,
        )
        terms = {"OnDemand": {"SKU.OFFER": {"priceDimensions": {"SKU.RATE": {"pricePerUnit": {"USD": "1"}}}}}}
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(
                plugin,
                "paginated_query_with_retries",
                return_value={"PriceList": [plugin.json.dumps({"sku": "SKU", "terms": terms})]},
            ) as query,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertEqual(
            require.call_args.args[3],
            {
                "get_products": (
                    "FormatVersion",
                    "ServiceCode",
                    "Filters",
                    "NextToken",
                )
            },
        )
        self.assertEqual(raised.exception.values["products"][0]["terms"], terms)
        query.assert_called_once_with(
            client,
            "get_products",
            Filters=[{"Field": "instanceType", "Type": "TERM_MATCH", "Value": "t3"}],
            FormatVersion="aws_v1",
            ServiceCode="AmazonEC2",
        )

    def test_new_filter_types_require_compatible_botocore(self):
        module = Mock(
            params={
                "filters": [{"field": "instanceType", "type": "EQUALS", "value": "t3"}],
                "format_version": "aws_v1",
                "max_results": None,
                "service_code": "AmazonEC2",
            },
            client=Mock(return_value=Mock()),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "paginated_query_with_retries", return_value={}),
        ):
            plugin.main()

        module.require_botocore_at_least.assert_called_once_with("1.39.5")

    def test_max_results_is_validated_when_requested(self):
        module = FakeModule(
            {
                "filters": [{"field": "instanceType", "type": "TERM_MATCH", "value": "t3"}],
                "format_version": "aws_v1",
                "max_results": 10,
                "service_code": "AmazonEC2",
            },
            client=Mock(),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "paginated_query_with_retries", return_value={}),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertIn("MaxResults", require.call_args.args[3]["get_products"])

    def test_rejects_max_results_outside_pricing_api_range(self):
        module = FakeModule(
            {
                "filters": [],
                "format_version": "aws_v1",
                "max_results": 101,
                "service_code": "AmazonEC2",
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("between 1 and 100", raised.exception.values["msg"])

    def test_rejects_more_than_50_filters(self):
        module = FakeModule(
            {
                "filters": [{"field": str(index), "type": "TERM_MATCH", "value": "x"} for index in range(51)],
                "format_version": "aws_v1",
                "max_results": None,
                "service_code": "AmazonEC2",
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["msg"], "filters must contain at most 50 entries")
