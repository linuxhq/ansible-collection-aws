#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_number
version_added: "1.9.6"
short_description: Manage AWS End User Messaging SMS phone numbers
description:
  - Requests and releases AWS End User Messaging SMS origination phone numbers.
  - This module maps to the Pinpoint SMS Voice V2 C(RequestPhoneNumber) API,
    the API behind C(aws pinpoint-sms-voice-v2 request-phone-number).
author:
  - Taylor Kimball (@tkimball83)
options:
  client_token:
    description:
      - Unique idempotency token for the phone number request.
      - When omitted, a deterministic token is generated from the request
        parameters.
    type: str
  deletion_protection_enabled:
    default: false
    description:
      - Whether deletion protection is enabled for the phone number.
    type: bool
  international_sending_enabled:
    description:
      - Whether international sending is enabled for the phone number.
      - This option requires AWS SDK support for the
        C(InternationalSendingEnabled) request parameter.
    type: bool
  iso_country_code:
    description:
      - The two-character ISO 3166-1 alpha-2 country or region code.
      - This is required when O(state=present).
    type: str
  message_type:
    choices:
      - PROMOTIONAL
      - TRANSACTIONAL
    description:
      - The type of messages sent from the phone number.
      - This is required when O(state=present).
    type: str
  number_capabilities:
    choices:
      - MMS
      - RCS
      - SMS
      - VOICE
    description:
      - The capabilities requested for the phone number.
      - This is required when O(state=present).
    elements: str
    type: list
  number_type:
    choices:
      - LONG_CODE
      - SIMULATOR
      - TEN_DLC
      - TOLL_FREE
    description:
      - The type of phone number to request.
      - When set to C(SIMULATOR), O(message_type) must be C(TRANSACTIONAL).
      - This is required when O(state=present).
    type: str
  opt_out_list_name:
    description:
      - The OptOutList name or ARN to associate with the phone number.
    type: str
  pool_id:
    description:
      - The pool ID or ARN to associate with the phone number.
    type: str
  phone_number_id:
    description:
      - The phone number ID to release.
      - This is required when O(state=absent).
    type: str
  registration_id:
    description:
      - The registration ID to attach to the phone number request.
    type: str
  state:
    description:
      - Whether the phone number should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the requested phone number.
    type: dict
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Request a transactional SMS long code
  linuxhq.aws.pinpoint_sms_voice_phone_number:
    iso_country_code: US
    message_type: TRANSACTIONAL
    number_capabilities:
      - SMS
    number_type: LONG_CODE
    tags:
      Name: molecule-sms

- name: Request a simulator phone number
  linuxhq.aws.pinpoint_sms_voice_phone_number:
    iso_country_code: US
    message_type: TRANSACTIONAL
    number_capabilities:
      - SMS
    number_type: SIMULATOR
    client_token: simulator-sms-request

- name: Ensure a phone number is absent
  linuxhq.aws.pinpoint_sms_voice_phone_number:
    phone_number_id: phone-0123456789abcdef0123456789abcdef
    state: absent
"""

RETURN = r"""
phone_number:
  description:
    - The requested or released phone number.
  returned: when available
  type: dict
phone_number_arn:
  description:
    - The ARN of the phone number.
  returned: when available
  type: str
phone_number_id:
  description:
    - The ID of the phone number.
  returned: when available
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import hashlib
import json

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def sorted_tag_list(tags):
    return sorted(ansible_dict_to_boto3_tag_list(tags), key=lambda tag: tag["Key"])


def request_parameters(module):
    return scrub_none_parameters(
        {
            "client_token": module.params["client_token"],
            "deletion_protection_enabled": module.params["deletion_protection_enabled"],
            "international_sending_enabled": module.params[
                "international_sending_enabled"
            ],
            "iso_country_code": module.params["iso_country_code"],
            "message_type": module.params["message_type"],
            "number_capabilities": module.params["number_capabilities"],
            "number_type": module.params["number_type"],
            "opt_out_list_name": module.params["opt_out_list_name"],
            "pool_id": module.params["pool_id"],
            "registration_id": module.params["registration_id"],
            "tags": (
                sorted_tag_list(module.params["tags"])
                if module.params["tags"] is not None
                else None
            ),
        }
    )


def deterministic_client_token(parameters):
    token_parameters = dict(parameters)
    token_parameters.pop("client_token", None)
    return hashlib.sha256(
        json.dumps(token_parameters, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def request_phone_number_parameters(client, module):
    parameters = request_parameters(module)
    if not parameters.get("client_token"):
        parameters["client_token"] = deterministic_client_token(parameters)

    request = snake_dict_to_camel_dict(parameters, capitalize_first=True)
    supported_parameters = set(
        client.meta.service_model.operation_model(
            "RequestPhoneNumber"
        ).input_shape.members
    )
    unsupported_parameters = sorted(set(request) - supported_parameters)
    if unsupported_parameters:
        module.fail_json(
            msg=(
                "Installed botocore does not support Pinpoint SMS Voice V2 "
                "RequestPhoneNumber parameter(s): "
                f"{', '.join(unsupported_parameters)}"
            )
        )
    return request


def validate_request(module):
    if (
        module.params["number_type"] == "SIMULATOR"
        and module.params["message_type"] != "TRANSACTIONAL"
    ):
        module.fail_json(
            msg="message_type must be TRANSACTIONAL when number_type is SIMULATOR"
        )


def desired_present_filters(module):
    filters = {
        "iso-country-code": module.params["iso_country_code"],
        "message-type": module.params["message_type"],
        "number-capability": module.params["number_capabilities"],
        "number-type": module.params["number_type"],
        "deletion-protection-enabled": module.params["deletion_protection_enabled"],
    }
    if module.params["opt_out_list_name"] is not None:
        filters["opt-out-list-name"] = module.params["opt_out_list_name"]
    return filters


def comparable_desired(module):
    desired = {
        "DeletionProtectionEnabled": module.params["deletion_protection_enabled"],
        "IsoCountryCode": module.params["iso_country_code"],
        "MessageType": module.params["message_type"],
        "NumberCapabilities": sorted(module.params["number_capabilities"] or []),
        "NumberType": module.params["number_type"],
    }
    for module_key, response_key in (
        ("international_sending_enabled", "InternationalSendingEnabled"),
        ("opt_out_list_name", "OptOutListName"),
        ("pool_id", "PoolId"),
        ("registration_id", "RegistrationId"),
    ):
        if module.params[module_key] is not None:
            desired[response_key] = module.params[module_key]
    return desired


def phone_number_matches_desired(module, phone_number):
    desired = comparable_desired(module)
    for key, value in desired.items():
        current = phone_number.get(key)
        if key == "NumberCapabilities":
            current = sorted(current or [])
        if current != value:
            return False
    return phone_number.get("Status") != "DELETED"


def phone_number_tags(client, module, phone_number):
    arn = phone_number.get("PhoneNumberArn")
    if not arn:
        return {}
    try:
        return boto3_tag_list_to_ansible_dict(
            client.list_tags_for_resource(
                ResourceArn=arn,
                aws_retry=True,
            ).get("Tags", [])
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 phone number {arn}"
        )


def phone_number_tags_match(client, module, phone_number):
    if module.params["tags"] is None:
        return True
    current_tags = phone_number_tags(client, module, phone_number)
    return all(
        current_tags.get(key) == value for key, value in module.params["tags"].items()
    )


def existing_phone_number(client, module):
    request = {
        "Filters": ansible_dict_to_boto3_filter_list(desired_present_filters(module)),
        "Owner": "SELF",
    }
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

    for phone_number in phone_numbers:
        if phone_number_matches_desired(
            module, phone_number
        ) and phone_number_tags_match(client, module, phone_number):
            if module.params["tags"] is not None:
                phone_number = dict(phone_number)
                phone_number["Tags"] = ansible_dict_to_boto3_tag_list(
                    phone_number_tags(client, module, phone_number)
                )
            return phone_number
    return None


def exit_result(module, changed, response):
    phone_number = boto3_resource_to_ansible_dict(
        response or {}, transform_tags=True, force_tags=False
    )
    result = {
        "changed": changed,
        "phone_number": phone_number,
        "phone_number_arn": phone_number.get("phone_number_arn"),
        "phone_number_id": phone_number.get("phone_number_id"),
        "state": module.params["state"],
    }
    result.update(phone_number)
    module.exit_json(**result)


def get_phone_number(client, module, phone_number_id):
    try:
        phone_numbers = client.describe_phone_numbers(
            PhoneNumberIds=[phone_number_id],
            aws_retry=True,
        ).get("PhoneNumbers", [])
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to describe Pinpoint SMS Voice V2 phone number "
                f"{phone_number_id}"
            ),
        )
    return phone_numbers[0] if phone_numbers else None


def release_phone_number(client, module, phone_number_id):
    try:
        return client.release_phone_number(
            PhoneNumberId=phone_number_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to release Pinpoint SMS Voice V2 phone number "
                f"{phone_number_id}"
            ),
        )


def ensure_absent(client, module):
    current = get_phone_number(client, module, module.params["phone_number_id"])
    changed = current is not None
    response = current

    if changed and not module.check_mode:
        response = release_phone_number(
            client, module, module.params["phone_number_id"]
        )

    exit_result(module, changed, response or current)


def ensure_present(client, module):
    validate_request(module)
    current = existing_phone_number(client, module)
    if current is not None:
        exit_result(module, False, current)

    request = request_phone_number_parameters(client, module)

    if module.check_mode:
        exit_result(module, True, request)

    try:
        response = client.request_phone_number(**request, aws_retry=True)
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to request Pinpoint SMS Voice V2 phone number"
        )

    exit_result(module, True, response)


def main():
    argument_spec = {
        "client_token": {"no_log": False, "type": "str"},
        "deletion_protection_enabled": {"default": False, "type": "bool"},
        "international_sending_enabled": {"type": "bool"},
        "iso_country_code": {"type": "str"},
        "message_type": {
            "choices": ["PROMOTIONAL", "TRANSACTIONAL"],
            "type": "str",
        },
        "number_capabilities": {
            "choices": ["MMS", "RCS", "SMS", "VOICE"],
            "elements": "str",
            "type": "list",
        },
        "number_type": {
            "choices": ["LONG_CODE", "SIMULATOR", "TEN_DLC", "TOLL_FREE"],
            "type": "str",
        },
        "opt_out_list_name": {"type": "str"},
        "phone_number_id": {"type": "str"},
        "pool_id": {"type": "str"},
        "registration_id": {"type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"type": "dict"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[
            (
                "state",
                "present",
                [
                    "iso_country_code",
                    "message_type",
                    "number_capabilities",
                    "number_type",
                ],
            ),
            ("state", "absent", ["phone_number_id"]),
        ],
        supports_check_mode=True,
    )

    client = module.client(
        "pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff()
    )

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
