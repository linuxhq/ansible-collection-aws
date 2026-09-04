#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_number
short_description: Manage aws end user messaging sms phone numbers
description:
  - Requests and releases AWS End User Messaging SMS origination phone numbers.
  - An existing active phone number matching the requested attributes and tags
    is adopted; otherwise a new phone number is requested.
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
      - This option is only used when requesting a new phone number; it is
        not used when matching existing phone numbers.
      - This option requires AWS SDK support for the
        C(InternationalSendingEnabled) request parameter.
    type: bool
  iso_country_code:
    description:
      - The two-character ISO 3166-1 alpha-2 country or region code.
      - This must be exactly two uppercase letters.
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
      - This must contain 1 to 4 capabilities.
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
  phone_number_id:
    description:
      - The phone number ID to release.
      - This is required when O(state=absent).
    type: str
  pool_id:
    description:
      - The pool ID or ARN to associate with the phone number.
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
      - This must contain at most 200 entries; keys must contain 1 to 128 characters and values at most 256 characters.
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
      - This must be 1 or greater.
    type: int
  wait_timeout:
    default: 300
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
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

import re
import time

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
)


def phone_number_tags(client, module, phone_number):
    arn = phone_number.get("PhoneNumberArn")

    if not arn:
        return {}

    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"list_tags_for_resource": ("ResourceArn",)},
    )
    try:
        response = client.list_tags_for_resource(
            ResourceArn=arn,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 phone number {arn}")

    tags = response.get("Tags") if isinstance(response, dict) else None
    if not isinstance(tags, list) or any(
        not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str)
        for tag in tags
    ):
        module.fail_json(msg=f"AWS returned malformed tags for Pinpoint SMS Voice V2 phone number {arn}")

    return boto3_tag_list_to_ansible_dict(tags)


def validate_phone_number(module, phone_number, context, required_fields=()):
    if (
        not isinstance(phone_number, dict)
        or not isinstance(phone_number.get("PhoneNumberId"), str)
        or not isinstance(phone_number.get("Status"), str)
        or any(not isinstance(phone_number.get(field), str) for field in required_fields)
    ):
        module.fail_json(msg=f"AWS returned a malformed Pinpoint SMS Voice V2 phone number while {context}")

    if "DeletionProtectionEnabled" in phone_number and not isinstance(phone_number["DeletionProtectionEnabled"], bool):
        module.fail_json(msg=f"AWS returned a malformed Pinpoint SMS Voice V2 phone number while {context}")
    if "NumberCapabilities" in phone_number and (
        not isinstance(phone_number["NumberCapabilities"], list)
        or any(not isinstance(capability, str) for capability in phone_number["NumberCapabilities"])
    ):
        module.fail_json(msg=f"AWS returned a malformed Pinpoint SMS Voice V2 phone number while {context}")

    return phone_number


def exit_result(module, changed, response):
    phone_number = boto3_resource_to_ansible_dict(response or {}, transform_tags=True, force_tags=False)
    result = {
        "changed": changed,
        "state": module.params["state"],
    }
    if phone_number:
        result["phone_number"] = phone_number
    if phone_number.get("phone_number_arn"):
        result["phone_number_arn"] = phone_number["phone_number_arn"]
    if phone_number.get("phone_number_id"):
        result["phone_number_id"] = phone_number["phone_number_id"]
    module.exit_json(**result)


def get_phone_number(client, module, phone_number_id):
    try:
        response = paginated_query_with_retries(
            client,
            "describe_phone_numbers",
            PhoneNumberIds=[phone_number_id],
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=("Unable to describe Pinpoint SMS Voice V2 phone number " f"{phone_number_id}"),
        )

    phone_numbers = response.get("PhoneNumbers") if isinstance(response, dict) else None
    if not isinstance(phone_numbers, list):
        module.fail_json(msg="AWS returned malformed Pinpoint SMS Voice V2 phone number data")
    if not phone_numbers:
        return None

    phone_number = validate_phone_number(module, phone_numbers[0], f"describing {phone_number_id}")
    if phone_number["PhoneNumberId"] != phone_number_id:
        module.fail_json(
            msg=f"AWS returned the wrong Pinpoint SMS Voice V2 phone number while describing {phone_number_id}"
        )
    return phone_number


def wait_for_phone_number_active(client, module, phone_number_id):
    wait_delay = module.params["wait_delay"]
    deadline = time.monotonic() + module.params["wait_timeout"]
    phone_number = {}

    while time.monotonic() < deadline:
        found_phone_number = get_phone_number(client, module, phone_number_id)
        if found_phone_number is None and module.params.get("state") == "absent":
            return {}
        phone_number = found_phone_number or {}
        status = phone_number.get("Status")

        if status == "ACTIVE":
            if (
                module.params.get("state") == "present"
                and module.params["tags"] is not None
                and phone_number.get("PhoneNumberArn")
            ):
                phone_number = dict(phone_number)
                phone_number["Tags"] = ansible_dict_to_boto3_tag_list(phone_number_tags(client, module, phone_number))
            return phone_number

        if status == "DELETED":
            if module.params.get("state") == "absent":
                return phone_number
            module.fail_json(
                msg=(
                    "AWS End User Messaging SMS phone number " f"{phone_number_id} was deleted before becoming active"
                ),
                phone_number=boto3_resource_to_ansible_dict(phone_number, transform_tags=False, force_tags=False),
                phone_number_id=phone_number_id,
                status=status,
            )
        time.sleep(min(wait_delay, max(0, deadline - time.monotonic())))

    module.fail_json(
        msg=("Timed out waiting for AWS End User Messaging SMS phone number " f"{phone_number_id} to become active"),
        phone_number=boto3_resource_to_ansible_dict(phone_number, transform_tags=False, force_tags=False),
        phone_number_id=phone_number_id,
        status=phone_number.get("Status"),
    )


def ensure_absent(client, module):
    phone_number_id = module.params["phone_number_id"]
    current = get_phone_number(client, module, phone_number_id)

    if current is not None and current.get("Status") == "DELETED":
        current = None

    changed = current is not None
    response = current

    if changed and not module.check_mode:
        if current.get("Status") != "ACTIVE":
            current = wait_for_phone_number_active(client, module, phone_number_id)

        if current.get("PoolId"):
            require_client_methods(
                module,
                client,
                "Pinpoint SMS Voice V2",
                {
                    "disassociate_origination_identity": (
                        "OriginationIdentity",
                        "PoolId",
                    )
                },
            )
            try:
                client.disassociate_origination_identity(
                    PoolId=current["PoolId"],
                    OriginationIdentity=phone_number_id,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                pass
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to disassociate Pinpoint SMS Voice V2 phone "
                        f"number {phone_number_id} from pool {current['PoolId']}"
                    ),
                )

        if current.get("DeletionProtectionEnabled"):
            require_client_methods(
                module,
                client,
                "Pinpoint SMS Voice V2",
                {
                    "update_phone_number": (
                        "DeletionProtectionEnabled",
                        "PhoneNumberId",
                    )
                },
            )
            try:
                current = client.update_phone_number(
                    PhoneNumberId=phone_number_id,
                    DeletionProtectionEnabled=False,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                exit_result(module, True, None)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to disable deletion protection for Pinpoint "
                        f"SMS Voice V2 phone number {phone_number_id}"
                    ),
                )

            validate_phone_number(module, current, "disabling deletion protection")
            wait_for_phone_number_active(client, module, phone_number_id)

        require_client_methods(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {"release_phone_number": ("PhoneNumberId",)},
        )
        try:
            response = client.release_phone_number(
                PhoneNumberId=phone_number_id,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            response = None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to release Pinpoint SMS Voice V2 phone number " f"{phone_number_id}"),
            )

        if response is not None:
            validate_phone_number(module, response, "releasing a phone number")
            response.pop("ResponseMetadata", None)

    exit_result(module, changed, response)


def ensure_present(client, module):
    deletion_protection_enabled = module.params["deletion_protection_enabled"]
    iso_country_code = module.params["iso_country_code"]
    message_type = module.params["message_type"]
    number_capabilities = module.params["number_capabilities"]
    number_type = module.params["number_type"]
    opt_out_list_name = module.params["opt_out_list_name"]
    pool_id = module.params["pool_id"]
    registration_id = module.params["registration_id"]
    tags = module.params["tags"]
    wait = module.params["wait"]
    filters = {
        "iso-country-code": iso_country_code,
        "message-type": message_type,
        "number-capability": number_capabilities,
        "number-type": number_type,
        "deletion-protection-enabled": deletion_protection_enabled,
    }
    if opt_out_list_name is not None:
        filters["opt-out-list-name"] = opt_out_list_name

    phone_numbers = query_list(
        module,
        client,
        "describe_phone_numbers",
        "PhoneNumbers",
        "Unable to describe Pinpoint SMS Voice V2 phone numbers",
        Filters=ansible_dict_to_boto3_filter_list(filters),
        Owner="SELF",
    )

    desired = {
        "DeletionProtectionEnabled": deletion_protection_enabled,
        "IsoCountryCode": iso_country_code,
        "MessageType": message_type,
        "NumberCapabilities": sorted(set(number_capabilities or [])),
        "NumberType": number_type,
    }
    for module_value, response_key in (
        (opt_out_list_name, "OptOutListName"),
        (pool_id, "PoolId"),
    ):
        if module_value is not None:
            desired[response_key] = module_value.rsplit("/", 1)[-1]
    if registration_id is not None:
        desired["RegistrationId"] = registration_id

    current = None
    for phone_number in phone_numbers:
        validate_phone_number(
            module,
            phone_number,
            "matching existing phone numbers",
            required_fields=(
                "IsoCountryCode",
                "MessageType",
                "NumberType",
            ),
        )
        if "DeletionProtectionEnabled" not in phone_number or "NumberCapabilities" not in phone_number:
            module.fail_json(
                msg="AWS returned a malformed Pinpoint SMS Voice V2 phone number while matching existing phone numbers"
            )
        if phone_number.get("Status") == "DELETED":
            continue

        matched = True
        for key, value in desired.items():
            current_value = phone_number.get(key)
            if key == "NumberCapabilities":
                current_value = sorted(set(current_value or []))
            if current_value != value:
                matched = False
                break

        if not matched:
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
        if wait and not module.check_mode and current.get("Status") != "ACTIVE":
            current = wait_for_phone_number_active(client, module, current["PhoneNumberId"])
        exit_result(module, False, current)

    parameters = scrub_none_parameters(
        {
            "client_token": module.params["client_token"],
            "deletion_protection_enabled": deletion_protection_enabled,
            "international_sending_enabled": module.params["international_sending_enabled"],
            "iso_country_code": iso_country_code,
            "message_type": message_type,
            "number_capabilities": sorted(set(number_capabilities)),
            "number_type": number_type,
            "opt_out_list_name": opt_out_list_name,
            "pool_id": pool_id,
            "registration_id": registration_id,
            "tags": (
                sorted(ansible_dict_to_boto3_tag_list(tags), key=lambda tag: tag["Key"]) if tags is not None else None
            ),
        }
    )
    request = snake_dict_to_camel_dict(parameters, capitalize_first=True)

    if module.check_mode:
        predicted = dict(request)
        predicted.pop("ClientToken", None)
        exit_result(module, True, predicted)

    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"request_phone_number": tuple(request)},
    )
    try:
        response = client.request_phone_number(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Unable to request Pinpoint SMS Voice V2 phone number")

    if not isinstance(response, dict):
        module.fail_json(msg="AWS did not return the requested Pinpoint SMS Voice V2 phone number")
    response.pop("ResponseMetadata", None)
    validate_phone_number(module, response, "requesting a phone number")

    if wait and response.get("Status") != "ACTIVE":
        response = wait_for_phone_number_active(client, module, response["PhoneNumberId"])

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

    state = module.params["state"]
    tags = module.params["tags"]

    if state == "present":
        if not re.fullmatch(r"[A-Z]{2}", module.params["iso_country_code"]):
            module.fail_json(msg="iso_country_code must be exactly two uppercase letters")

        if not 1 <= len(set(module.params["number_capabilities"])) <= 4:
            module.fail_json(msg="number_capabilities must contain 1 to 4 capabilities")

        if module.params["number_type"] == "SIMULATOR" and module.params["message_type"] != "TRANSACTIONAL":
            module.fail_json(msg="message_type must be TRANSACTIONAL when number_type is SIMULATOR")

    require_valid_tags(module, tags if state == "present" else None, 200)
    require_positive_wait_bounds(module, always=state == "absent")

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())
    describe_parameters = ("MaxResults", "NextToken")
    if state == "present":
        describe_parameters += ("Filters", "Owner")
    if state == "absent":
        describe_parameters += ("PhoneNumberIds",)
    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"describe_phone_numbers": describe_parameters},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
