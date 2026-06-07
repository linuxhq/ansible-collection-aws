#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_number_info
short_description: Gather information about aws end user messaging sms phone numbers
description:
  - Gathers information about AWS End User Messaging SMS phone numbers.
  - This module maps to the Pinpoint SMS Voice V2 C(DescribePhoneNumbers) API,
    the API behind C(aws pinpoint-sms-voice-v2 describe-phone-numbers).
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing phone numbers.
      - Filter names and values are passed to the Pinpoint SMS Voice V2
        C(DescribePhoneNumbers) API.
    type: dict
  max_results:
    description:
      - The maximum number of results returned by each API call.
      - The module follows pagination and returns all matching phone numbers.
    type: int
  owner:
    choices:
      - SELF
      - SHARED
    default: SELF
    description:
      - The phone number owner to query.
      - This is not sent when O(phone_number_ids) is set because
        C(DescribePhoneNumbers) does not allow both parameters together.
    type: str
  phone_number_ids:
    description:
      - Phone number IDs used to limit the result set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about End User Messaging SMS phone numbers
  linuxhq.aws.pinpoint_sms_voice_phone_number_info:

- name: Gather information about selected phone numbers
  linuxhq.aws.pinpoint_sms_voice_phone_number_info:
    phone_number_ids:
      - phone-0123456789abcdef0123456789abcdef

- name: Gather information about simulator SMS phone numbers
  linuxhq.aws.pinpoint_sms_voice_phone_number_info:
    filters:
      iso-country-code: US
      message-type: TRANSACTIONAL
      number-capability: SMS
      number-type: SIMULATOR
"""

RETURN = r"""
phone_number_ids:
  description:
    - A list of matching phone number IDs.
  returned: always
  type: list
  elements: str
phone_numbers:
  description:
    - A list of End User Messaging SMS phone numbers.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
)


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "max_results": {"type": "int"},
        "owner": {"choices": ["SELF", "SHARED"], "default": "SELF", "type": "str"},
        "phone_number_ids": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client(
        "pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff()
    )

    request = {}
    if module.params["max_results"] is not None:
        request["MaxResults"] = module.params["max_results"]
    if module.params["phone_number_ids"]:
        request["PhoneNumberIds"] = module.params["phone_number_ids"]
    elif module.params["owner"] is not None:
        request["Owner"] = module.params["owner"]
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])

    try:
        supported_parameters = set(
            get_boto3_client_method_parameters(client, "describe_phone_numbers")
        )
    except Exception:
        module.fail_json(
            msg=(
                "Installed botocore does not support Pinpoint SMS Voice V2 "
                "DescribePhoneNumbers"
            )
        )

    unsupported_parameters = sorted(set(request) - supported_parameters)

    if unsupported_parameters:
        module.fail_json(
            msg=(
                "Installed botocore does not support Pinpoint SMS Voice V2 "
                "DescribePhoneNumbers parameter(s): "
                f"{', '.join(unsupported_parameters)}"
            )
        )

    try:
        phone_numbers = paginated_query_with_retries(
            client,
            "describe_phone_numbers",
            **request,
        ).get("PhoneNumbers", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to describe Pinpoint SMS Voice V2 phone numbers"
        )

    normalized_phone_numbers = []
    for phone_number in phone_numbers:
        arn = phone_number.get("PhoneNumberArn")
        tags = []

        if arn:
            try:
                tags = client.list_tags_for_resource(
                    ResourceArn=arn,
                    aws_retry=True,
                ).get("Tags", [])
            except is_boto3_error_code("ResourceNotFoundException"):
                tags = []
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to list tags for Pinpoint SMS Voice V2 phone number "
                        f"{arn}"
                    ),
                )

        normalized_phone_numbers.append(
            boto3_resource_to_ansible_dict(
                dict(phone_number, Tags=tags),
                transform_tags=True,
                force_tags=False,
            )
        )

    phone_number_ids = []
    for phone_number in normalized_phone_numbers:
        if phone_number.get("phone_number_id"):
            phone_number_ids.append(phone_number["phone_number_id"])

    module.exit_json(
        changed=False,
        phone_number_ids=phone_number_ids,
        phone_numbers=normalized_phone_numbers,
    )


if __name__ == "__main__":
    main()
