#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_number
version_added: '1.9.0'
short_description: Manage aws end user messaging sms phone numbers
description:
  - Requests and releases AWS End User Messaging SMS origination phone numbers.
  - Without O(phone_number_id), an existing phone number matching the requested
    attributes is adopted; otherwise a new phone number is requested.
  - Matching uses the attributes fixed when a number is requested, O(iso_country_code),
    O(message_type), O(number_capabilities), O(number_type), O(pool_id), and O(registration_id).
  - When O(tags) contains a C(Name) key, matching also requires an equal C(Name) tag, and the
    module fails if more than one phone number matches. Other tags are not used for matching.
  - When O(tags) is omitted, the first phone number matching the fixed attributes is adopted.
  - When O(tags) has no C(Name) key, the module fails if more than one phone number matches the
    fixed attributes, instead of retagging an arbitrary number. Set a C(Name) tag to identify a
    specific number.
  - O(tags) other than C(Name) are converged on the matched number according to O(purge_tags).
  - O(deletion_protection_enabled), O(international_sending_enabled), and O(opt_out_list_name)
    are updated in place on the matched number with C(UpdatePhoneNumber).
  - With O(phone_number_id), that number is updated; a missing number or mismatched
    request attributes fail without requesting a replacement.
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
    description:
      - Whether deletion protection is enabled for the phone number.
      - When omitted while requesting a number, AWS disables deletion protection.
      - When omitted for an existing number, the current setting is left unchanged.
      - This cannot be changed on an existing number that is associated with a pool.
    type: bool
  international_sending_enabled:
    description:
      - Whether international sending is enabled for the phone number.
      - When omitted for an existing number, the current setting is left unchanged.
      - This cannot be changed on an existing number that is associated with a pool.
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
      - When omitted for an existing number, the current OptOutList is left unchanged.
      - This cannot be changed on an existing number that is associated with a pool.
    type: str
  phone_number_id:
    description:
      - The phone number ID to manage or release.
      - Set this with O(state=present) to update tags and settings on a specific existing number.
      - This is required when O(state=absent).
      - With O(state=absent), a number in a pool is disassociated from the pool
        before it is released.
      - With O(state=absent), the module fails without changes, including in
        check mode, when the number is the last phone number in its pool,
        because AWS does not allow it to be disassociated. Delete the pool with
        M(linuxhq.aws.pinpoint_sms_voice_phone_pool) first. Sender IDs in the
        pool do not count as phone numbers, and this module never deletes pools.
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
  wait:
    default: true
    description:
      - Whether to wait for a requested or matched phone number status to become C(ACTIVE).
      - Even when O(wait=false), the module waits for a matched number that is not C(ACTIVE)
        before updating its settings or tags.
      - When O(state=absent), the module always waits for the number to become C(ACTIVE)
        before and between the steps that disassociate it from its pool, disable deletion
        protection, and release it.
    type: bool
  wait_delay:
    default: 5
    description:
      - The delay in seconds between polling attempts whenever the module waits.
      - This must be 1 or greater and is validated even when O(wait=false).
    type: int
  wait_timeout:
    default: 300
    description:
      - The maximum number of seconds for each wait the module performs.
      - This must be 1 or greater and is validated even when O(wait=false).
    type: int
notes:
  - O(tags) accepts at most 200 entries; keys must contain 1 to 128 characters
    and values at most 256 characters.
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
  contains:
    created_timestamp:
      description: The time the phone number was created.
      returned: when returned by AWS
      type: str
    deletion_protection_enabled:
      description: Whether deletion protection is enabled.
      returned: when returned by AWS
      type: bool
    international_sending_enabled:
      description: Whether international sending is enabled.
      returned: when returned by AWS
      type: bool
    iso_country_code:
      description: The two-character ISO country code.
      returned: when returned by AWS
      type: str
    message_type:
      description: The type of messages sent from the phone number.
      returned: when returned by AWS
      type: str
    monthly_leasing_price:
      description: The monthly price to lease the phone number.
      returned: when returned by AWS
      type: str
    number_capabilities:
      description: The phone number capabilities.
      returned: when returned by AWS
      type: list
      elements: str
    number_type:
      description: The phone number type.
      returned: when returned by AWS
      type: str
    opt_out_list_name:
      description: The OptOutList associated with the phone number.
      returned: when returned by AWS
      type: str
    phone_number:
      description: The phone number in E.164 format.
      returned: when returned by AWS
      type: str
    phone_number_arn:
      description: The phone number ARN.
      returned: when returned by AWS
      type: str
    phone_number_id:
      description: The phone number ID.
      returned: when returned by AWS
      type: str
    pool_id:
      description: The pool the phone number is associated with.
      returned: when associated with a pool
      type: str
    registration_id:
      description: The registration associated with the phone number.
      returned: when associated with a registration
      type: str
    self_managed_opt_outs_enabled:
      description: Whether self-managed opt-outs are enabled.
      returned: when returned by AWS
      type: bool
    status:
      description: The phone number status.
      returned: when returned by AWS
      type: str
      sample: ACTIVE
    tags:
      description: The phone number tags with key case preserved.
      returned: when O(tags) is provided and O(state=present)
      type: dict
    two_way_enabled:
      description: Whether two-way messaging is enabled.
      returned: when returned by AWS
      type: bool
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
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.pinpoint_sms_voice import (
    is_last_phone_number,
    is_last_phone_number_conflict,
    last_phone_number_message,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    require_valid_tag_list,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
)

SETTING_OPTIONS = {
    "DeletionProtectionEnabled": "deletion_protection_enabled",
    "InternationalSendingEnabled": "international_sending_enabled",
    "OptOutListName": "opt_out_list_name",
}


def phone_number_tags(client, module, phone_number, changed=False):
    """List tags; changed reports whether the phone number was already modified, for failure results."""
    arn = phone_number.get("PhoneNumberArn")

    if not arn:
        return {}

    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"list_tags_for_resource": ("ResourceArn",)},
        changed=changed,
    )
    try:
        response = client.list_tags_for_resource(
            ResourceArn=arn,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e, changed=changed, msg=f"Unable to list tags for Pinpoint SMS Voice V2 phone number {arn}"
        )

    tags = require_valid_tag_list(
        module,
        response.get("Tags") if isinstance(response, dict) else None,
        f"AWS returned malformed tags for Pinpoint SMS Voice V2 phone number {arn}",
        changed=changed,
    )

    return boto3_tag_list_to_ansible_dict(tags)


def validate_phone_number(module, phone_number, context, required_fields=(), changed=False):
    """Validate a phone number; changed reports whether it was already modified, for failure results."""
    msg = f"AWS returned a malformed Pinpoint SMS Voice V2 phone number while {context}"
    if (
        not isinstance(phone_number, dict)
        or not isinstance(phone_number.get("PhoneNumberId"), str)
        or not isinstance(phone_number.get("Status"), str)
        or any(not isinstance(phone_number.get(field), str) for field in required_fields)
    ):
        module.fail_json(changed=changed, msg=msg)

    if "DeletionProtectionEnabled" in phone_number and not isinstance(phone_number["DeletionProtectionEnabled"], bool):
        module.fail_json(changed=changed, msg=msg)

    if "NumberCapabilities" in phone_number and (
        not isinstance(phone_number["NumberCapabilities"], list)
        or any(not isinstance(capability, str) for capability in phone_number["NumberCapabilities"])
    ):
        module.fail_json(changed=changed, msg=msg)

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


def get_phone_number(client, module, phone_number_id, changed=False):
    """Describe a phone number; changed reports whether it was already modified, for failure results."""
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
            changed=changed,
            msg=f"Unable to describe Pinpoint SMS Voice V2 phone number {phone_number_id}",
        )

    phone_numbers = response.get("PhoneNumbers") if isinstance(response, dict) else None
    if not isinstance(phone_numbers, list):
        module.fail_json(changed=changed, msg="AWS returned malformed Pinpoint SMS Voice V2 phone number data")

    if not phone_numbers:
        return None

    phone_number = validate_phone_number(module, phone_numbers[0], f"describing {phone_number_id}", changed=changed)
    if phone_number["PhoneNumberId"] != phone_number_id:
        module.fail_json(
            changed=changed,
            msg=f"AWS returned the wrong Pinpoint SMS Voice V2 phone number while describing {phone_number_id}",
        )

    return phone_number


def wait_for_phone_number_active(client, module, phone_number_id, tags=None, changed=False):
    """Wait for a phone number; changed reports whether it was already modified, for failure results."""
    wait_delay = module.params["wait_delay"]
    deadline = time.monotonic() + module.params["wait_timeout"]
    phone_number = {}

    while time.monotonic() < deadline:
        found_phone_number = get_phone_number(client, module, phone_number_id, changed=changed)
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
                if tags is None:
                    tags = ansible_dict_to_boto3_tag_list(
                        phone_number_tags(client, module, phone_number, changed=changed)
                    )

                phone_number["Tags"] = tags

            return phone_number

        if status == "DELETED":
            if module.params.get("state") == "absent":
                return phone_number

            module.fail_json(
                changed=changed,
                msg=f"AWS End User Messaging SMS phone number {phone_number_id} was deleted before becoming active",
                phone_number=boto3_resource_to_ansible_dict(phone_number, transform_tags=False, force_tags=False),
                phone_number_id=phone_number_id,
                status=status,
            )

        time.sleep(min(wait_delay, max(0, deadline - time.monotonic())))

    module.fail_json(
        changed=changed,
        msg=f"Timed out waiting for AWS End User Messaging SMS phone number {phone_number_id} to become active",
        phone_number=boto3_resource_to_ansible_dict(phone_number, transform_tags=False, force_tags=False),
        phone_number_id=phone_number_id,
        status=phone_number.get("Status"),
    )


def updatable_settings_delta(module, current):
    updates = {}
    for option, field in (
        ("deletion_protection_enabled", "DeletionProtectionEnabled"),
        ("international_sending_enabled", "InternationalSendingEnabled"),
    ):
        if module.params[option] is not None and current.get(field) != module.params[option]:
            updates[field] = module.params[option]

    # OptOutListName accepts a name or ARN; DescribePhoneNumbers returns the name.
    opt_out_list_name = module.params["opt_out_list_name"]
    if opt_out_list_name is not None and current.get("OptOutListName") != opt_out_list_name.rsplit("/", 1)[-1]:
        updates["OptOutListName"] = opt_out_list_name

    return updates


def phone_number_changes(client, module, current):
    """Return the number with its tags and the settings and tag changes it needs."""
    tags = module.params["tags"]
    updates = updatable_settings_delta(module, current)

    # Tags are read before any write, so tagging failures before any change report changed=False.
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        current = dict(current)
        if "Tags" not in current:
            current["Tags"] = ansible_dict_to_boto3_tag_list(phone_number_tags(client, module, current))

        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict(current["Tags"]), tags, purge_tags=module.params["purge_tags"]
        )

    return current, updates, tags_to_set, tag_keys_to_unset


def update_phone_number(client, module, current, updates):
    phone_number_id = current["PhoneNumberId"]
    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"update_phone_number": ("PhoneNumberId",) + tuple(updates)},
    )
    try:
        response = client.update_phone_number(PhoneNumberId=phone_number_id, **updates, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to update Pinpoint SMS Voice V2 phone number {phone_number_id}")

    response = validate_phone_number(module, response, "updating a phone number", changed=True)
    response.pop("ResponseMetadata", None)
    return dict(current, **response)


def disassociate_failure_message(phone_number_id, pool_id):
    return f"Unable to disassociate Pinpoint SMS Voice V2 phone number {phone_number_id} from pool {pool_id}"


def pool_is_deleting(client, module, pool_id):
    try:
        response = paginated_query_with_retries(client, "describe_pools", PoolIds=[pool_id])
    except is_boto3_error_code("ResourceNotFoundException"):
        return True
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe Pinpoint SMS Voice V2 pool {pool_id}")

    pools = response.get("Pools") if isinstance(response, dict) else None
    if not isinstance(pools, list) or any(not isinstance(pool, dict) for pool in pools):
        module.fail_json(msg=f"AWS returned malformed data while describing Pinpoint SMS Voice V2 pool {pool_id}")

    return not pools or pools[0].get("Status") == "DELETING"


def require_not_last_pool_phone_number(client, module, current):
    """Fail without changes when AWS would reject disassociating the number as the last one in its pool."""
    pool_id = current["PoolId"]
    phone_number_id = current["PhoneNumberId"]
    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {
            "describe_pools": ("PoolIds",),
            "list_pool_origination_identities": ("PoolId",),
        },
    )
    try:
        response = paginated_query_with_retries(client, "list_pool_origination_identities", PoolId=pool_id)
    except is_boto3_error_code("ResourceNotFoundException"):
        return
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to list origination identities for Pinpoint SMS Voice V2 pool {pool_id}")

    originations = response.get("OriginationIdentities") if isinstance(response, dict) else None
    if not isinstance(originations, list) or any(not isinstance(origination, dict) for origination in originations):
        module.fail_json(msg=f"AWS returned malformed origination identities for Pinpoint SMS Voice V2 pool {pool_id}")

    identities = tuple(filter(None, (phone_number_id, current.get("PhoneNumberArn"))))
    # Deleting a pool disassociates its numbers, so the number can be released once its pool is going away.
    if is_last_phone_number(originations, identities) and not pool_is_deleting(client, module, pool_id):
        module.fail_json(changed=False, msg=last_phone_number_message(phone_number_id, pool_id))


def ensure_absent(client, module):
    phone_number_id = module.params["phone_number_id"]
    current = get_phone_number(client, module, phone_number_id)

    if current is not None and current.get("Status") == "DELETED":
        current = None

    changed = current is not None
    response = current

    # Only the pool module deletes pools, so the last phone number in a pool is never released here.
    if changed and module.check_mode and current.get("PoolId"):
        require_not_last_pool_phone_number(client, module, current)

    if changed and not module.check_mode:
        if current.get("Status") != "ACTIVE":
            current = wait_for_phone_number_active(client, module, phone_number_id)
            # Deleted elsewhere during the wait; this run changed nothing.
            if not current or current.get("Status") == "DELETED":
                exit_result(module, False, None)

        if current.get("PoolId"):
            require_not_last_pool_phone_number(client, module, current)

        # Every write is checked before the first one, so an older botocore fails without modifying anything.
        methods = {"release_phone_number": ("PhoneNumberId",)}
        if current.get("PoolId"):
            methods["disassociate_origination_identity"] = ("OriginationIdentity", "PoolId")

        if current.get("DeletionProtectionEnabled"):
            methods["update_phone_number"] = ("DeletionProtectionEnabled", "PhoneNumberId")

        require_client_methods(module, client, "Pinpoint SMS Voice V2", methods)

        # Failures after the first successful change report changed=True.
        mutated = False
        if current.get("PoolId"):
            try:
                client.disassociate_origination_identity(
                    PoolId=current["PoolId"],
                    OriginationIdentity=phone_number_id,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                pass
            except is_boto3_error_code("ConflictException") as e:
                if is_last_phone_number_conflict(e):
                    module.fail_json(changed=False, msg=last_phone_number_message(phone_number_id, current["PoolId"]))

                module.fail_json_aws(e, msg=disassociate_failure_message(phone_number_id, current["PoolId"]))
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=disassociate_failure_message(phone_number_id, current["PoolId"]))
            else:
                mutated = True
                current = wait_for_phone_number_active(client, module, phone_number_id, changed=True)
                if not current or current.get("Status") == "DELETED":
                    exit_result(module, True, None)

        if current.get("DeletionProtectionEnabled"):
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
                    changed=mutated,
                    msg=(
                        "Unable to disable deletion protection for Pinpoint "
                        f"SMS Voice V2 phone number {phone_number_id}"
                    ),
                )

            mutated = True
            validate_phone_number(module, current, "disabling deletion protection", changed=True)
            wait_for_phone_number_active(client, module, phone_number_id, changed=True)

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
                changed=mutated,
                msg=f"Unable to release Pinpoint SMS Voice V2 phone number {phone_number_id}",
            )

        if response is not None:
            validate_phone_number(module, response, "releasing a phone number", changed=True)
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
    }

    if module.params["phone_number_id"]:
        phone_number = get_phone_number(client, module, module.params["phone_number_id"])
        phone_numbers = [phone_number] if phone_number is not None else []
    else:
        phone_numbers = query_list(
            module,
            client,
            "describe_phone_numbers",
            "PhoneNumbers",
            "Unable to describe Pinpoint SMS Voice V2 phone numbers",
            Filters=ansible_dict_to_boto3_filter_list(filters),
            Owner="SELF",
        )

    # Match only attributes fixed by RequestPhoneNumber; updatable settings converge below.
    desired = {
        "IsoCountryCode": iso_country_code,
        "MessageType": message_type,
        "NumberCapabilities": sorted(set(number_capabilities or [])),
        "NumberType": number_type,
    }
    if pool_id is not None:
        desired["PoolId"] = pool_id.rsplit("/", 1)[-1]

    if registration_id is not None:
        desired["RegistrationId"] = registration_id

    # Without phone_number_id, a requested Name tag identifies the number; other tags converge below.
    name = None if module.params["phone_number_id"] else (tags or {}).get("Name")
    matches = []
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

        if name is None:
            matches.append(phone_number)
            if tags is None:
                break

            continue

        current_tags = phone_number_tags(client, module, phone_number)
        if current_tags.get("Name") == name:
            matches.append(dict(phone_number, Tags=ansible_dict_to_boto3_tag_list(current_tags)))

    if name is None and len(matches) > 1:
        # Retagging needs one unambiguous number when no Name tag identifies it.
        module.fail_json(
            msg=(
                "Multiple Pinpoint SMS Voice V2 phone numbers matched the requested attributes; "
                "set a Name tag or phone_number_id to choose one: "
                + ", ".join(sorted(phone_number["PhoneNumberId"] for phone_number in matches))
            )
        )

    if len(matches) > 1:
        module.fail_json(
            msg=(
                f"Multiple Pinpoint SMS Voice V2 phone numbers matched name {name}: "
                + ", ".join(sorted(phone_number["PhoneNumberId"] for phone_number in matches))
            )
        )

    current = matches[0] if matches else None
    if current is not None:
        current, updates, tags_to_set, tag_keys_to_unset = phone_number_changes(client, module, current)
        if (
            not module.check_mode
            and current.get("Status") != "ACTIVE"
            and (wait or updates or tags_to_set or tag_keys_to_unset)
        ):
            # Changes always wait for ACTIVE, even when wait=false, and are recalculated from the settled number.
            current = wait_for_phone_number_active(client, module, current["PhoneNumberId"], tags=current.get("Tags"))
            current, updates, tags_to_set, tag_keys_to_unset = phone_number_changes(client, module, current)

        if updates and current.get("PoolId"):
            options = ", ".join(SETTING_OPTIONS[field] for field in updates)
            module.fail_json(
                msg=f"Unable to update {options} for Pinpoint SMS Voice V2 phone number {current['PhoneNumberId']} in pool {current['PoolId']}"
            )

        tags_changed = bool(tags_to_set or tag_keys_to_unset)
        if tags_changed and not module.check_mode:
            if not current.get("PhoneNumberArn"):
                module.fail_json(msg="AWS did not return the phone number ARN required for tagging")

            methods = {}
            if tags_to_set:
                methods["tag_resource"] = ("ResourceArn", "Tags")

            if tag_keys_to_unset:
                methods["untag_resource"] = ("ResourceArn", "TagKeys")

            require_client_methods(module, client, "Pinpoint SMS Voice V2", methods)

        changed = bool(updates) or tags_changed
        if updates:
            if module.check_mode:
                # Project OptOutListName as DescribePhoneNumbers returns it, the name rather than the ARN.
                projected = dict(updates)
                if "OptOutListName" in projected:
                    projected["OptOutListName"] = projected["OptOutListName"].rsplit("/", 1)[-1]

                current = dict(current, **projected)
            else:
                current = update_phone_number(client, module, current, updates)

        if tags_changed and not module.check_mode:
            reconcile_arn_tags(
                module,
                client,
                current["PhoneNumberArn"],
                tags_to_set,
                tag_keys_to_unset,
                "phone number",
                changed=bool(updates),
            )

        if tags is not None:
            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

        exit_result(module, changed, current)

    if module.params["phone_number_id"]:
        module.fail_json(msg="The specified phone number was not found or does not match the requested attributes")

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
        module.fail_json(changed=True, msg="AWS did not return the requested Pinpoint SMS Voice V2 phone number")

    response.pop("ResponseMetadata", None)
    validate_phone_number(module, response, "requesting a phone number", changed=True)

    if wait and response.get("Status") != "ACTIVE":
        response = wait_for_phone_number_active(client, module, response["PhoneNumberId"], changed=True)

    exit_result(module, True, response)


def main():
    argument_spec = {
        "client_token": {"no_log": False, "type": "str"},
        "deletion_protection_enabled": {"type": "bool"},
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
        "purge_tags": {"default": True, "type": "bool"},
        "registration_id": {"type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
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
    require_positive_wait_bounds(module, always=True)

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())
    # Waits and re-reads describe by PhoneNumberIds on every path.
    describe_parameters = ("MaxResults", "NextToken", "PhoneNumberIds")
    if state == "present" and not module.params["phone_number_id"]:
        describe_parameters += ("Filters", "Owner")

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
