#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_number
short_description: Manage aws end user messaging sms phone numbers
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
      - When omitted, AWS generates an idempotency token for the request.
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
  wait:
    default: true
    description:
      - Whether to wait for the phone number status to become C(ACTIVE).
    type: bool
  wait_delay:
    default: 5
    description:
      - The delay between polling attempts when O(wait=true).
    type: int
  wait_timeout:
    default: 300
    description:
      - The maximum number of seconds to wait when O(wait=true).
    type: int
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

import time

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
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
        phone_numbers = paginated_query_with_retries(
            client,
            "describe_phone_numbers",
            PhoneNumberIds=[phone_number_id],
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


def wait_for_phone_number_active(client, module, phone_number_id):
    wait_delay = max(1, module.params["wait_delay"])
    deadline = time.monotonic() + module.params["wait_timeout"]
    phone_number = {}

    while time.monotonic() < deadline:
        phone_number = get_phone_number(client, module, phone_number_id) or {}
        status = phone_number.get("Status")
        if status == "ACTIVE":
            if module.params["tags"] is not None and phone_number.get("PhoneNumberArn"):
                phone_number = dict(phone_number)
                phone_number["Tags"] = ansible_dict_to_boto3_tag_list(
                    phone_number_tags(client, module, phone_number)
                )
            return phone_number
        if status == "DELETED":
            module.fail_json(
                msg=(
                    "AWS End User Messaging SMS phone number "
                    f"{phone_number_id} was deleted before becoming active"
                ),
                phone_number=boto3_resource_to_ansible_dict(
                    phone_number, transform_tags=False, force_tags=False
                ),
                phone_number_id=phone_number_id,
                status=status,
            )
        time.sleep(wait_delay)

    module.fail_json(
        msg=(
            "Timed out waiting for AWS End User Messaging SMS phone number "
            f"{phone_number_id} to become active"
        ),
        phone_number=boto3_resource_to_ansible_dict(
            phone_number, transform_tags=False, force_tags=False
        ),
        phone_number_id=phone_number_id,
        status=phone_number.get("Status"),
    )


def ensure_absent(client, module):
    phone_number_id = module.params["phone_number_id"]
    current = get_phone_number(client, module, phone_number_id)
    changed = current is not None
    response = current

    if changed and not module.check_mode:
        try:
            response = client.release_phone_number(
                PhoneNumberId=phone_number_id,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            response = None
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to release Pinpoint SMS Voice V2 phone number "
                    f"{phone_number_id}"
                ),
            )

    exit_result(module, changed, response or current)


def ensure_present(client, module):
    deletion_protection_enabled = module.params["deletion_protection_enabled"]
    international_sending_enabled = module.params["international_sending_enabled"]
    iso_country_code = module.params["iso_country_code"]
    message_type = module.params["message_type"]
    number_capabilities = module.params["number_capabilities"]
    number_type = module.params["number_type"]
    opt_out_list_name = module.params["opt_out_list_name"]
    pool_id = module.params["pool_id"]
    registration_id = module.params["registration_id"]
    tags = module.params["tags"]
    wait = module.params["wait"]

    if number_type == "SIMULATOR" and message_type != "TRANSACTIONAL":
        module.fail_json(
            msg="message_type must be TRANSACTIONAL when number_type is SIMULATOR"
        )

    filters = {
        "iso-country-code": iso_country_code,
        "message-type": message_type,
        "number-capability": number_capabilities,
        "number-type": number_type,
        "deletion-protection-enabled": deletion_protection_enabled,
    }
    if opt_out_list_name is not None:
        filters["opt-out-list-name"] = opt_out_list_name

    request = {
        "Filters": ansible_dict_to_boto3_filter_list(filters),
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

    desired = {
        "DeletionProtectionEnabled": deletion_protection_enabled,
        "IsoCountryCode": iso_country_code,
        "MessageType": message_type,
        "NumberCapabilities": sorted(number_capabilities or []),
        "NumberType": number_type,
    }
    for module_value, response_key in (
        (international_sending_enabled, "InternationalSendingEnabled"),
        (opt_out_list_name, "OptOutListName"),
        (pool_id, "PoolId"),
        (registration_id, "RegistrationId"),
    ):
        if module_value is not None:
            desired[response_key] = module_value

    current = None
    for phone_number in phone_numbers:
        matched = True
        for key, value in desired.items():
            current_value = phone_number.get(key)
            if key == "NumberCapabilities":
                current_value = sorted(current_value or [])
            if current_value != value:
                matched = False
                break

        if not matched:
            continue

        if phone_number.get("Status") == "DELETED":
            continue

        if tags is None:
            current = phone_number
            break

        current_tags = phone_number_tags(client, module, phone_number)
        tags_match = True
        for key, value in tags.items():
            if current_tags.get(key) != value:
                tags_match = False
                break

        if not tags_match:
            continue

        current = dict(phone_number)
        current["Tags"] = ansible_dict_to_boto3_tag_list(current_tags)
        break

    if current is not None:
        if wait and current.get("Status") != "ACTIVE":
            current = wait_for_phone_number_active(
                client, module, current["PhoneNumberId"]
            )
        exit_result(module, False, current)

    parameters = scrub_none_parameters(
        {
            "client_token": module.params["client_token"],
            "deletion_protection_enabled": deletion_protection_enabled,
            "international_sending_enabled": international_sending_enabled,
            "iso_country_code": iso_country_code,
            "message_type": message_type,
            "number_capabilities": number_capabilities,
            "number_type": number_type,
            "opt_out_list_name": opt_out_list_name,
            "pool_id": pool_id,
            "registration_id": registration_id,
            "tags": (
                sorted(ansible_dict_to_boto3_tag_list(tags), key=lambda tag: tag["Key"])
                if tags is not None
                else None
            ),
        }
    )
    request = snake_dict_to_camel_dict(parameters, capitalize_first=True)

    if module.check_mode:
        exit_result(module, True, request)

    try:
        response = client.request_phone_number(**request, aws_retry=True)
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to request Pinpoint SMS Voice V2 phone number"
        )

    if wait and response.get("Status") != "ACTIVE" and response.get("PhoneNumberId"):
        response = wait_for_phone_number_active(
            client, module, response["PhoneNumberId"]
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
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 5, "type": "int"},
        "wait_timeout": {"default": 300, "type": "int"},
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

    state = module.params["state"]
    tags = module.params["tags"]
    method_names = {"describe_phone_numbers"}
    if state == "present":
        method_names.add("request_phone_number")
        if tags is not None:
            method_names.add("list_tags_for_resource")
    elif state == "absent":
        method_names.add("release_phone_number")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=(
                    "Installed botocore does not support Pinpoint SMS Voice V2 "
                    f"{method_name}"
                )
            )

    required_method_parameters = {
        "describe_phone_numbers": {
            "Filters",
            "MaxResults",
            "NextToken",
            "Owner",
            "PhoneNumberIds",
        },
        "list_tags_for_resource": {"ResourceArn"},
        "release_phone_number": {"PhoneNumberId"},
        "request_phone_number": {
            "ClientToken",
            "DeletionProtectionEnabled",
            "IsoCountryCode",
            "MessageType",
            "NumberCapabilities",
            "NumberType",
            "OptOutListName",
            "PoolId",
            "RegistrationId",
        },
    }
    if (
        state == "present"
        and module.params["international_sending_enabled"] is not None
    ):
        required_method_parameters["request_phone_number"].add(
            "InternationalSendingEnabled"
        )
    if state == "present" and tags is not None:
        required_method_parameters["request_phone_number"].add("Tags")

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Pinpoint SMS Voice V2 "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
