from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_pricing_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["service_code"]["default"] == "AmazonEC2"


def test_empty_filters_query_every_product_like_the_api():
    module = FakeModule(
        {
            "filters": [],
            "format_version": "aws_v1",
            "max_results": None,
            "service_code": "AmazonEC2",
        },
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"PriceList": []}) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["products"] == []
    query.assert_called_once_with(module._client, "get_products", FormatVersion="aws_v1", ServiceCode="AmazonEC2")


def test_product_terms_use_snake_case_fields_and_keep_codes():
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
    terms = {
        "OnDemand": {
            "SKU.OFFER": {
                "effectiveDate": "2026-09-01T00:00:00Z",
                "offerTermCode": "OFFER",
                "priceDimensions": {
                    "SKU.OFFER.RATE": {"appliesTo": [], "pricePerUnit": {"USD": "1"}, "rateCode": "SKU.OFFER.RATE"}
                },
                "termAttributes": {"LeaseContractLength": "3yr"},
            }
        }
    }
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "paginated_query_with_retries",
            return_value={"PriceList": [plugin.json.dumps({"sku": "SKU", "terms": terms})]},
        ) as query,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert require.call_args.args[3] == {
        "get_products": (
            "FormatVersion",
            "ServiceCode",
            "Filters",
            "NextToken",
        )
    }
    assert raised.value.values["products"][0]["terms"] == {
        "on_demand": {
            "SKU.OFFER": {
                "effective_date": "2026-09-01T00:00:00Z",
                "offer_term_code": "OFFER",
                "price_dimensions": {
                    "SKU.OFFER.RATE": {
                        "applies_to": [],
                        "price_per_unit": {"USD": "1"},
                        "rate_code": "SKU.OFFER.RATE",
                    }
                },
                "term_attributes": {"lease_contract_length": "3yr"},
            }
        }
    }
    query.assert_called_once_with(
        client,
        "get_products",
        Filters=[{"Field": "instanceType", "Type": "TERM_MATCH", "Value": "t3"}],
        FormatVersion="aws_v1",
        ServiceCode="AmazonEC2",
    )


def test_new_filter_types_require_compatible_botocore():
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
        patch.object(plugin, "paginated_query_with_retries", return_value={"PriceList": []}),
    ):
        plugin.main()

    module.require_botocore_at_least.assert_called_once_with("1.39.5")


def test_max_results_is_validated_when_requested():
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
        patch.object(plugin, "paginated_query_with_retries", return_value={"PriceList": []}),
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert "MaxResults" in require.call_args.args[3]["get_products"]


def test_rejects_max_results_outside_pricing_api_range():
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
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "between 1 and 100" in raised.value.values["msg"]


def test_rejects_more_than_50_filters():
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
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "filters must contain at most 50 entries"


def test_rejects_invalid_price_list_response():
    params = {
        "filters": [{"field": "instanceType", "type": "TERM_MATCH", "value": "t3"}],
        "format_version": "aws_v1",
        "max_results": None,
        "service_code": "AmazonEC2",
    }
    for response in ({}, {"PriceList": None}, None):
        module = FakeModule(params, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "paginated_query_with_retries", return_value=response),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert "invalid price list" in raised.value.values["msg"]


def test_rejects_invalid_product_payloads():
    params = {
        "filters": [{"field": "instanceType", "type": "TERM_MATCH", "value": "t3"}],
        "format_version": "aws_v1",
        "max_results": None,
        "service_code": "AmazonEC2",
    }
    for product, message in ((None, "Unable to parse"), ("not-json", "Unable to parse"), ("[]", "not an object")):
        module = FakeModule(params, client=Mock())
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "paginated_query_with_retries", return_value={"PriceList": [product]}),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.main()

        assert message in raised.value.values["msg"]


@pytest.mark.parametrize("region", ["us-east-1", "eu-central-1", "us-west-2"])
def test_pricing_client_uses_the_selected_region(region):
    module = Mock(
        params={
            "filters": [{"field": "instanceType", "type": "TERM_MATCH", "value": "t3.micro"}],
            "format_version": "aws_v1",
            "max_results": None,
            "service_code": "AmazonEC2",
        },
        region=region,
        client=Mock(return_value=Mock()),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"PriceList": []}),
    ):
        plugin.main()

    # module.client() connects to module.region; the module no longer overrides it.
    assert module.client.call_args.args == ("pricing",)
    assert "region" not in module.client.call_args.kwargs


def test_region_is_required():
    module = FakeModule(
        {
            "filters": [{"field": "instanceType", "type": "TERM_MATCH", "value": "t3.micro"}],
            "format_version": "aws_v1",
            "max_results": None,
            "service_code": "AmazonEC2",
        },
        region=None,
        client=Mock(),
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "region is required" in raised.value.values["msg"]
