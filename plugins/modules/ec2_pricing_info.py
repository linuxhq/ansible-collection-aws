#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_pricing_info
short_description: Gather information about aws pricing products
description:
  - Gathers AWS Price List product information.
  - This module maps to the AWS Pricing C(GetProducts) API, the API behind
    C(aws pricing get-products).
  - The Pricing API endpoint is queried in C(us-east-1). Use filters such as
    C(regionCode) or C(location) for product-specific regional pricing data.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - Filters to apply when gathering products.
      - Filter entries are passed to the AWS Pricing C(GetProducts) API.
      - When omitted or empty, no API call is made and an empty product list
        is returned.
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
    region: us-west-2
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def pricing_filters(filters):
    return [
        {
            "Field": pricing_filter["field"],
            "Type": pricing_filter.get("type") or "TERM_MATCH",
            "Value": pricing_filter["value"],
        }
        for pricing_filter in filters or []
    ]


def build_request(module):
    request = {}
    if module.params["format_version"] is not None:
        request["FormatVersion"] = module.params["format_version"]
    if module.params["max_results"] is not None:
        request["MaxResults"] = module.params["max_results"]
    if module.params["service_code"] is not None:
        request["ServiceCode"] = module.params["service_code"]
    filters = pricing_filters(module.params["filters"])
    if filters:
        request["Filters"] = filters
    return request


def parse_products(module, price_list):
    products = []
    for product in price_list:
        try:
            products.append(json.loads(product))
        except ValueError as e:
            module.fail_json(msg=f"Unable to parse AWS Price List product: {e}")
    return products


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

    if not module.params["filters"]:
        module.exit_json(
            changed=False,
            format_version=module.params["format_version"],
            products=[],
            service_code=module.params["service_code"],
        )

    client = module.client(
        "pricing",
        retry_decorator=AWSRetry.jittered_backoff(),
        region="us-east-1",
    )

    try:
        response = paginated_query_with_retries(
            client,
            "get_products",
            **build_request(module),
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get AWS Price List products")

    module.exit_json(
        changed=False,
        format_version=response.get("FormatVersion", module.params["format_version"]),
        products=boto3_resource_list_to_ansible_dict(
            parse_products(module, response.get("PriceList", [])),
            transform_tags=False,
            force_tags=False,
        ),
        service_code=module.params["service_code"],
    )


if __name__ == "__main__":
    main()
