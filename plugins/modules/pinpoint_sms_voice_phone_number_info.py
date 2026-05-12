#!/usr/bin/python
# Copyright: Taylor Kimball
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

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def build_request(module):
    phone_number_ids = module.params["phone_number_ids"] or None
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "max_results": module.params["max_results"],
                "owner": module.params["owner"] if not phone_number_ids else None,
                "phone_number_ids": phone_number_ids,
            },
            capitalize_first=True,
        )
    )
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])
    return request


def phone_number_tags(client, module, phone_number):
    arn = phone_number.get("PhoneNumberArn")
    if not arn:
        return []
    try:
        return client.list_tags_for_resource(
            ResourceArn=arn,
            aws_retry=True,
        ).get("Tags", [])
    except is_boto3_error_code("ResourceNotFoundException"):
        return []
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 phone number {arn}"
        )


def normalize_phone_number(client, module, phone_number):
    return boto3_resource_to_ansible_dict(
        dict(
            phone_number,
            Tags=phone_number_tags(client, module, phone_number),
        ),
        transform_tags=True,
        force_tags=False,
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

    try:
        phone_numbers = paginated_query_with_retries(
            client,
            "describe_phone_numbers",
            **build_request(module),
        ).get("PhoneNumbers", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to describe Pinpoint SMS Voice V2 phone numbers"
        )

    phone_numbers = [
        normalize_phone_number(client, module, phone_number)
        for phone_number in phone_numbers
    ]
    module.exit_json(
        changed=False,
        phone_number_ids=[
            phone_number["phone_number_id"]
            for phone_number in phone_numbers
            if phone_number.get("phone_number_id")
        ],
        phone_numbers=phone_numbers,
    )


if __name__ == "__main__":
    main()
