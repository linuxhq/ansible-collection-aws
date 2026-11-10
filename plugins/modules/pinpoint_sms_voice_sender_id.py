#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_sender_id
version_added: '2.6.0'
short_description: Manage AWS End User Messaging SMS sender IDs
description:
  - Requests, updates, and releases AWS End User Messaging SMS sender IDs.
  - A sender ID is identified by O(sender_id) and O(iso_country_code).
  - O(message_types) are fixed when a sender ID is requested. When an existing sender ID has
    different message types, the module fails without changes; release the sender ID and request
    it again to change them.
  - O(deletion_protection_enabled) is updated in place with C(UpdateSenderId).
  - Sender IDs in countries that require registration are not supported; AWS rejects the request
    and the module reports the AWS error.
  - This module maps to the Pinpoint SMS Voice V2 C(RequestSenderId) API,
    the API behind C(aws pinpoint-sms-voice-v2 request-sender-id).
author:
  - Taylor Kimball (@tkimball83)
options:
  deletion_protection_enabled:
    description:
      - Whether deletion protection is enabled for the sender ID.
      - When omitted while requesting a sender ID, AWS disables deletion protection.
      - When omitted for an existing sender ID, the current setting is left unchanged.
      - With O(state=absent), this is ignored. The module fails without changes when the sender ID
        has deletion protection enabled; disable it with O(state=present) first.
    type: bool
  iso_country_code:
    description:
      - The two-character ISO 3166-1 alpha-2 country or region code of the sender ID.
      - This must be exactly two uppercase letters.
    required: true
    type: str
  message_types:
    choices:
      - PROMOTIONAL
      - TRANSACTIONAL
    description:
      - The types of messages the sender ID sends.
      - When omitted while requesting a sender ID, AWS chooses the message types.
      - When omitted for an existing sender ID, its message types are not compared.
      - When provided, this must not be empty.
      - AWS cannot change the message types of an existing sender ID, so the module fails when they
        differ from these.
    elements: str
    type: list
  sender_id:
    description:
      - The sender ID to request, update, or release.
      - This must contain 1 to 11 letters, numbers, hyphens, or underscores.
    required: true
    type: str
  state:
    description:
      - Whether the sender ID should exist.
      - With O(state=absent), AWS fails the release of a sender ID that is associated with a pool;
        disassociate it with M(linuxhq.aws.pinpoint_sms_voice_phone_pool_associate) first.
    choices:
      - absent
      - present
    default: present
    type: str
notes:
  - O(tags) accepts at most 200 entries; keys must contain 1 to 128 characters
    and values at most 256 characters, and both may contain only letters,
    numbers, spaces, C(_), C(.), C(:), C(/), C(=), C(+), C(-), and C(@).
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  diff_mode:
    description: Diff mode is not supported.
    support: none
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
"""

EXAMPLES = r"""
- name: Request a transactional sender ID
  linuxhq.aws.pinpoint_sms_voice_sender_id:
    sender_id: EXAMPLE
    iso_country_code: DE
    message_types:
      - TRANSACTIONAL
    tags:
      Team: messaging

- name: Enable deletion protection on a sender ID
  linuxhq.aws.pinpoint_sms_voice_sender_id:
    sender_id: EXAMPLE
    iso_country_code: DE
    deletion_protection_enabled: true

- name: Ensure a sender ID is released
  linuxhq.aws.pinpoint_sms_voice_sender_id:
    sender_id: EXAMPLE
    iso_country_code: DE
    state: absent
"""

RETURN = r"""
sender_id:
  description:
    - The requested, updated, or released sender ID.
  returned: when the sender ID exists, is requested, or is released
  type: dict
  contains:
    deletion_protection_enabled:
      description: Whether deletion protection is enabled.
      returned: when returned by AWS
      type: bool
    iso_country_code:
      description: The two-character ISO country code.
      returned: always
      type: str
    message_types:
      description:
        - The types of messages the sender ID sends, as AWS returns them.
        - C(DescribeSenderIds) returns them in title case, such as C(Transactional).
      returned: when returned by AWS
      type: list
      elements: str
    messaging_limits:
      description:
        - The messaging limits that apply to the sender ID.
        - Map keys are converted to snake_case like other keys, so C(SMS) is
          returned as C(sms) and C(T-MOBILE) as C(t-mobile).
      returned: when returned by AWS
      type: dict
      contains:
        daily_message_caps:
          description: The advisory maximum number of messages that can be sent per day, keyed by carrier.
          returned: when a daily message cap applies
          type: dict
        rate_limits:
          description: The maximum send rate in messages per second, keyed by capability.
          returned: when returned by AWS
          type: dict
    monthly_leasing_price:
      description: The monthly price, in US dollars, to lease the sender ID.
      returned: when returned by AWS
      type: str
    pricing_tier:
      description: The pricing model of the sender ID.
      returned: when returned by AWS
      type: str
    registered:
      description: Whether the sender ID is registered.
      returned: when returned by AWS
      type: bool
    registration_id:
      description: The registration associated with the sender ID.
      returned: when associated with a registration
      type: str
    sender_id:
      description: The sender ID.
      returned: always
      type: str
    sender_id_arn:
      description: The sender ID ARN.
      returned: when returned by AWS
      type: str
    tags:
      description: The sender ID tags with key case preserved.
      returned: when O(state=present)
      type: dict
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.pinpoint_sms_voice import list_tags
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    require_no_reserved_tag_keys,
    require_resulting_tag_limit,
    require_valid_tags,
)

SERVICE = "Pinpoint SMS Voice V2"


def describe_name(module):
    return f"{SERVICE} sender ID {module.params['sender_id']} in {module.params['iso_country_code']}"


def validate_sender_id(module, sender_id, context, changed=False):
    """Validate a sender ID; changed reports whether it was already modified, for failure results."""
    msg = f"AWS returned a malformed {SERVICE} sender ID while {context}"
    if (
        not isinstance(sender_id, dict)
        or not isinstance(sender_id.get("SenderId"), str)
        or not isinstance(sender_id.get("IsoCountryCode"), str)
        or not isinstance(sender_id.get("SenderIdArn"), str)
    ):
        module.fail_json(changed=changed, msg=msg)

    if "DeletionProtectionEnabled" in sender_id and not isinstance(sender_id["DeletionProtectionEnabled"], bool):
        module.fail_json(changed=changed, msg=msg)

    if "MessageTypes" in sender_id and (
        not isinstance(sender_id["MessageTypes"], list)
        or any(not isinstance(message_type, str) for message_type in sender_id["MessageTypes"])
    ):
        module.fail_json(changed=changed, msg=msg)

    # Compared without case, so a sender ID AWS stores with different letter case is still recognized.
    if (sender_id["SenderId"].upper(), sender_id["IsoCountryCode"]) != (
        module.params["sender_id"].upper(),
        module.params["iso_country_code"],
    ):
        module.fail_json(changed=changed, msg=f"AWS returned the wrong {SERVICE} sender ID while {context}")

    sender_id = dict(sender_id)
    sender_id.pop("ResponseMetadata", None)
    return sender_id


def exit_result(module, changed, sender_id):
    result = {"changed": changed, "state": module.params["state"]}
    if sender_id:
        result["sender_id"] = boto3_resource_to_ansible_dict(sender_id, transform_tags=True, force_tags=False)

    module.exit_json(**result)


def get_sender_id(client, module):
    try:
        response = paginated_query_with_retries(
            client,
            "describe_sender_ids",
            SenderIds=[
                {
                    "IsoCountryCode": module.params["iso_country_code"],
                    "SenderId": module.params["sender_id"],
                }
            ],
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        # Live: DescribeSenderIds answers ResourceNotFoundException for a sender ID that does not exist.
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe {describe_name(module)}")

    sender_ids = response.get("SenderIds") if isinstance(response, dict) else None
    if not isinstance(sender_ids, list):
        module.fail_json(msg=f"AWS returned malformed {SERVICE} sender ID data")

    if not sender_ids:
        return None

    return validate_sender_id(module, sender_ids[0], "describing it")


def require_message_types(module, current):
    """Fail without changes when the existing sender ID's message types differ from the requested ones."""
    desired = module.params["message_types"]
    if desired is None:
        return

    # Live: DescribeSenderIds returns message types in title case, such as Transactional, so compare without case.
    existing = sorted({message_type.upper() for message_type in current.get("MessageTypes") or []})
    if existing != sorted(set(desired)):
        module.fail_json(
            msg=(
                f"Unable to change the message types of {describe_name(module)} from "
                f"{', '.join(existing) or 'none'} to {', '.join(sorted(set(desired)))}; AWS does not allow message "
                "types to change, so release the sender ID and request it again"
            )
        )


def update_sender_id(client, module, current):
    try:
        response = client.update_sender_id(
            SenderId=module.params["sender_id"],
            IsoCountryCode=module.params["iso_country_code"],
            DeletionProtectionEnabled=module.params["deletion_protection_enabled"],
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to update {describe_name(module)}")

    response = validate_sender_id(module, response, "updating it", changed=True)
    # UpdateSenderId omits the messaging limits and pricing tier DescribeSenderIds returns.
    return dict(current, **response)


def ensure_present(client, module, current):
    deletion_protection_enabled = module.params["deletion_protection_enabled"]
    tags = module.params["tags"]

    if current is None:
        request = scrub_none_parameters(
            {
                "DeletionProtectionEnabled": deletion_protection_enabled,
                "IsoCountryCode": module.params["iso_country_code"],
                "MessageTypes": sorted(set(module.params["message_types"] or [])) or None,
                "SenderId": module.params["sender_id"],
                "Tags": ansible_dict_to_boto3_tag_list(tags) if tags else None,
            }
        )

        if module.check_mode:
            # A real run returns the RequestSenderId response; predict only what the request determines.
            predicted = dict(request, DeletionProtectionEnabled=bool(deletion_protection_enabled))
            predicted["Tags"] = request.get("Tags", [])
            exit_result(module, True, predicted)

        require_client_methods(module, client, SERVICE, {"request_sender_id": tuple(request)})
        try:
            response = client.request_sender_id(**request, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to request {describe_name(module)}")

        response = validate_sender_id(module, response, "requesting it", changed=True)
        response.setdefault("Tags", request.get("Tags", []))
        exit_result(module, True, response)

    require_message_types(module, current)

    arn = current["SenderIdArn"]
    require_client_methods(module, client, SERVICE, {"list_tags_for_resource": ("ResourceArn",)})
    current = dict(current, Tags=list_tags(client, module, arn, "sender ID"))
    current_tags = boto3_tag_list_to_ansible_dict(current["Tags"])
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(current_tags, tags, purge_tags=module.params["purge_tags"])
        require_resulting_tag_limit(module, current_tags, tags_to_set, tag_keys_to_unset, 200, f"{SERVICE} sender ID")

    update = deletion_protection_enabled is not None and current.get("DeletionProtectionEnabled") != (
        deletion_protection_enabled
    )
    tags_changed = bool(tags_to_set or tag_keys_to_unset)
    changed = update or tags_changed

    if module.check_mode:
        if update:
            current["DeletionProtectionEnabled"] = deletion_protection_enabled

        exit_result(module, changed, apply_tag_deltas(current, tags_to_set, tag_keys_to_unset))

    # Every write is checked before the first one, so an older botocore fails without modifying anything.
    methods = {}
    if update:
        methods["update_sender_id"] = ("DeletionProtectionEnabled", "IsoCountryCode", "SenderId")

    if tags_to_set:
        methods["tag_resource"] = ("ResourceArn", "Tags")

    if tag_keys_to_unset:
        methods["untag_resource"] = ("ResourceArn", "TagKeys")

    require_client_methods(module, client, SERVICE, methods)

    if update:
        current = update_sender_id(client, module, current)

    if tags_changed:
        reconcile_arn_tags(module, client, arn, tags_to_set, tag_keys_to_unset, f"{SERVICE} sender ID", changed=update)

    exit_result(module, changed, apply_tag_deltas(current, tags_to_set, tag_keys_to_unset))


def ensure_absent(client, module, current):
    if current is None:
        exit_result(module, False, None)

    if current.get("DeletionProtectionEnabled"):
        module.fail_json(
            msg=(
                f"Unable to release {describe_name(module)} because deletion protection is enabled; "
                "set deletion_protection_enabled to false with state=present first"
            )
        )

    if module.check_mode:
        # A real run returns the ReleaseSenderId response, and botocore drops the members its model lacks, so keep
        # only the described fields that response models.
        released_fields = client.meta.service_model.shape_for("ReleaseSenderIdResult").members
        exit_result(module, True, {key: value for key, value in current.items() if key in released_fields})

    require_client_methods(module, client, SERVICE, {"release_sender_id": ("IsoCountryCode", "SenderId")})
    try:
        response = client.release_sender_id(
            SenderId=module.params["sender_id"],
            IsoCountryCode=module.params["iso_country_code"],
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        # Released elsewhere since it was described.
        exit_result(module, False, None)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to release {describe_name(module)}")

    exit_result(module, True, validate_sender_id(module, response, "releasing it", changed=True))


def main():
    argument_spec = {
        "deletion_protection_enabled": {"type": "bool"},
        "iso_country_code": {"required": True, "type": "str"},
        "message_types": {
            "choices": ["PROMOTIONAL", "TRANSACTIONAL"],
            "elements": "str",
            "type": "list",
        },
        "purge_tags": {"default": True, "type": "bool"},
        "sender_id": {"required": True, "type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)

    # required counts only supplied keys, so an explicit null passes it.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,11}", module.params["sender_id"] or ""):
        module.fail_json(msg="sender_id must contain 1 to 11 letters, numbers, hyphens, or underscores")

    if not re.fullmatch(r"[A-Z]{2}", module.params["iso_country_code"] or ""):
        module.fail_json(msg="iso_country_code must be exactly two uppercase letters")

    if module.params["state"] == "present":
        if module.params["message_types"] == []:
            module.fail_json(msg="message_types must not be empty")

        require_valid_tags(module, module.params["tags"], 200, restricted_characters=True)
        # Live: SMS Voice V2 rejects these keys, which an existing sender ID would reach after UpdateSenderId.
        require_no_reserved_tag_keys(module, module.params["tags"] or {})

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(module, client, SERVICE, {"describe_sender_ids": ("MaxResults", "NextToken", "SenderIds")})
    current = get_sender_id(client, module)

    if module.params["state"] == "present":
        ensure_present(client, module, current)

    if module.params["state"] == "absent":
        ensure_absent(client, module, current)


if __name__ == "__main__":
    main()
