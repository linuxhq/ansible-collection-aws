#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_pricing_info
version_added: "1.9.0"
short_description: Gather information about AWS pricing products
description:
  - Gathers AWS Price List product information.
  - This module maps to the AWS Pricing C(GetProducts) API, the API behind
    C(aws pricing get-products).
  - Requires a region. The Pricing API is served from C(us-east-1),
    C(eu-central-1), and C(ap-south-1).
  - The endpoint region does not limit the products returned. Use filters such as
    C(regionCode) or C(location) for product-specific regional pricing data.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - Filters to apply when gathering products.
      - Filter entries are passed to the AWS Pricing C(GetProducts) API.
      - This must contain at most 50 entries.
      - When omitted or empty, every product for O(service_code) is returned,
        which can be very large.
    elements: dict
    suboptions:
      field:
        description:
          - The product metadata field to filter against.
        required: true
        type: str
      type:
        choices:
          - ANY_OF
          - CONTAINS
          - EQUALS
          - NONE_OF
          - TERM_MATCH
        default: TERM_MATCH
        description:
          - The pricing filter type.
          - Values other than C(TERM_MATCH) require botocore 1.39.5 or later.
        type: str
      value:
        description:
          - The filter value.
        required: true
        type: str
    type: list
  format_version:
    default: aws_v1
    description:
      - The format version for the returned price list.
    type: str
  max_results:
    description:
      - The maximum number of results returned by each C(GetProducts) API call.
      - This must be between C(1) and C(100).
      - The module follows pagination and returns all matching products.
    type: int
  service_code:
    default: AmazonEC2
    description:
      - The AWS service code to query.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only retrieves information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
"""

EXAMPLES = r"""
- name: Gather Amazon EC2 pricing products
  linuxhq.aws.ec2_pricing_info:
    filters:
      - field: instanceType
        value: t3.micro
      - field: location
        value: US East (N. Virginia)
      - field: operatingSystem
        value: Linux
      - field: tenancy
        value: Shared

- name: Gather Oregon EC2 pricing from the default Pricing API endpoint
  linuxhq.aws.ec2_pricing_info:
    filters:
      - field: instanceType
        value: t3.micro
      - field: regionCode
        value: us-west-2
      - field: operatingSystem
        value: Linux
      - field: tenancy
        value: Shared

- name: Gather pricing products for another service
  linuxhq.aws.ec2_pricing_info:
    service_code: AmazonRDS
    filters:
      - field: instanceType
        value: db.t3.micro
      - field: location
        value: US East (N. Virginia)
"""

RETURN = r"""
format_version:
  description:
    - The returned price list format version.
  returned: always
  type: str
products:
  description:
    - A list of parsed AWS Price List products.
    - Keys, including those in C(terms), are returned in snake_case and values
      are returned unchanged.
    - Offer term codes, rate codes, and currency codes used as keys in C(terms)
      keep the case returned by the Price List API.
  returned: always
  type: list
  elements: dict
service_code:
  description:
    - The queried AWS service code.
  returned: always
  type: str
"""

import json

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def snake_name(name):
    return next(iter(camel_dict_to_snake_dict({name: None})))


def normalize_terms(terms):
    """Snake-case term keys while keeping offer term, rate, and currency code keys as AWS returns them."""
    if not isinstance(terms, dict):
        return terms

    return {
        snake_name(term_type): (
            {code: normalize_offer_term(offer) for code, offer in offers.items()}
            if isinstance(offers, dict)
            else offers
        )
        for term_type, offers in terms.items()
    }


def normalize_offer_term(offer):
    if not isinstance(offer, dict):
        return offer

    result = camel_dict_to_snake_dict({key: value for key, value in offer.items() if key != "priceDimensions"})
    dimensions = offer.get("priceDimensions")
    if isinstance(dimensions, dict):
        result["price_dimensions"] = {
            rate_code: normalize_price_dimension(dimension) for rate_code, dimension in dimensions.items()
        }
    elif "priceDimensions" in offer:
        result["price_dimensions"] = dimensions

    return result


def normalize_price_dimension(dimension):
    if not isinstance(dimension, dict):
        return dimension

    result = camel_dict_to_snake_dict({key: value for key, value in dimension.items() if key != "pricePerUnit"})
    if "pricePerUnit" in dimension:
        result["price_per_unit"] = dimension["pricePerUnit"]

    return result


def main():
    argument_spec = {
        "filters": {
            "elements": "dict",
            "options": {
                "field": {"required": True, "type": "str"},
                "type": {
                    "choices": [
                        "ANY_OF",
                        "CONTAINS",
                        "EQUALS",
                        "NONE_OF",
                        "TERM_MATCH",
                    ],
                    "default": "TERM_MATCH",
                    "type": "str",
                },
                "value": {"required": True, "type": "str"},
            },
            "type": "list",
        },
        "format_version": {"default": "aws_v1", "type": "str"},
        "max_results": {"type": "int"},
        "service_code": {"default": "AmazonEC2", "type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    filters = module.params["filters"] or []
    format_version = module.params["format_version"]
    max_results = module.params["max_results"]
    service_code = module.params["service_code"]

    if max_results is not None and not 1 <= max_results <= 100:
        module.fail_json(msg="max_results must be between 1 and 100")

    if len(filters) > 50:
        module.fail_json(msg="filters must contain at most 50 entries")

    if not module.region:
        module.fail_json(
            msg="region is required; the Pricing API is served from us-east-1, eu-central-1, and ap-south-1"
        )

    client = module.client("pricing", retry_decorator=AWSRetry.jittered_backoff())

    if any(pricing_filter["type"] != "TERM_MATCH" for pricing_filter in filters):
        module.require_botocore_at_least("1.39.5")

    request = scrub_none_parameters(
        {
            "FormatVersion": format_version,
            "MaxResults": max_results,
            "ServiceCode": service_code,
        }
    )

    request_filters = [
        {
            "Field": pricing_filter["field"],
            "Type": pricing_filter["type"],
            "Value": pricing_filter["value"],
        }
        for pricing_filter in filters
    ]

    if request_filters:
        request["Filters"] = request_filters

    require_client_methods(
        module,
        client,
        "AWS Pricing",
        {"get_products": tuple(request) + ("NextToken",)},
    )

    try:
        response = paginated_query_with_retries(
            client,
            "get_products",
            **request,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Unable to get AWS Price List products")

    price_list = response.get("PriceList") if isinstance(response, dict) else None
    if not isinstance(price_list, list):
        module.fail_json(msg="AWS Pricing returned an invalid price list")

    products = []
    for product in price_list:
        try:
            parsed = json.loads(product)
        except (TypeError, ValueError) as e:
            module.fail_json(msg=f"Unable to parse AWS Price List product: {e}")

        if not isinstance(parsed, dict):
            module.fail_json(msg="AWS Pricing returned a product that is not an object")

        normalized = boto3_resource_to_ansible_dict(
            parsed,
            transform_tags=False,
            force_tags=False,
        )

        if "terms" in normalized:
            normalized["terms"] = normalize_terms(parsed.get("terms"))

        products.append(normalized)

    module.exit_json(
        changed=False,
        format_version=format_version,
        products=products,
        service_code=service_code,
    )


if __name__ == "__main__":
    main()
