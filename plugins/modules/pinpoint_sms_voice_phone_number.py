#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_number
version_added: '1.9.0'
short_description: Manage AWS End User Messaging SMS phone numbers
description:
  - Requests and releases AWS End User Messaging SMS origination phone numbers.
  - Without O(phone_number_id), an existing phone number matching the requested
    attributes and O(name) is adopted; otherwise a new phone number is requested.
  - Without O(phone_number_id), the module requires botocore 1.35.26 or later.
  - Matching uses the attributes fixed when a number is requested, O(iso_country_code),
    O(message_type), O(number_capabilities), O(number_type), and O(registration_id), the
    pool the number is currently in, O(pool_id), which can change after the request, and a
    C(Name) tag equal to O(name). The module fails if more than one phone number matches.
    Other tags are not used for matching.
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
      - AWS answers a request that repeats an earlier request's token and parameters with the number that request
        returned, even after that number was released or its pool or C(Name) tag changed. The module then fails
        without requesting a number; use a new token for each request, or set O(phone_number_id) to manage the
        existing number.
      - AWS rejects a request that reuses a token with other parameters, such as other attributes, O(pool_id), or
        C(Name) tag, with a C(ConflictException).
    type: str
  deletion_protection_enabled:
    description:
      - Whether deletion protection is enabled for the phone number.
      - When omitted while requesting a number, AWS disables deletion protection.
      - When omitted for an existing number, the current setting is left unchanged.
      - This cannot be changed on an existing number that is associated with a pool.
      - With O(state=absent), the module disables deletion protection on a protected number before releasing it.
    type: bool
  international_sending_enabled:
    description:
      - Whether international sending is enabled for the phone number.
      - When omitted for an existing number, the current setting is left unchanged.
      - This cannot be changed on an existing number that is associated with a pool.
      - Requires botocore 1.40.14 or later.
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
      - This is required when O(state=present).
    elements: str
    type: list
  name:
    description:
      - Name of the phone number.
      - This is used as the C(Name) tag and overrides any C(Name) entry in O(tags).
      - Without O(phone_number_id), this identifies the phone number to manage or release.
      - Without O(phone_number_id) and with O(state=absent), the module releases the phone number
        whose C(Name) tag equals this, and fails without changes when more than one phone number
        has that tag.
    required: true
    type: str
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
      - This must not be empty when provided with O(state=present).
    type: str
  phone_number_id:
    description:
      - The phone number ID or ARN to manage or release.
      - Set this with O(state=present) to update tags and settings on a specific existing number.
      - Set this with O(state=absent) to release a specific number instead of the one found by O(name).
      - With O(state=absent), a number in a pool is disassociated from the pool
        before it is released.
      - With O(state=absent), the module fails without changes, including in
        check mode, when the number is the only origination identity in its
        pool, because AWS does not allow it to be disassociated. Delete the pool
        with M(linuxhq.aws.pinpoint_sms_voice_phone_pool) first. This module
        never deletes pools.
      - When the pool is already being deleted, that number is released
        instead, and check mode reports that change, because deleting the pool
        disassociates it.
    type: str
  pool_id:
    description:
      - The pool ID or ARN to associate with the phone number.
      - This must not be empty when provided with O(state=present).
    type: str
  registration_id:
    description:
      - The registration ID or ARN to attach to the phone number request.
      - This must not be empty when provided with O(state=present).
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
    and values at most 256 characters, and both may contain only letters,
    numbers, spaces, C(_), C(.), C(:), C(/), C(=), C(+), C(-), and C(@).
  - The module always manages the C(Name) tag from O(name), even when O(tags)
    is omitted. This tag overrides any C(Name) entry in O(tags), counts
    toward the 200-tag limit, and follows the same value rules. Other tags are
    left unchanged when O(tags) is omitted.
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
    iso_country_code: CA
    message_type: TRANSACTIONAL
    name: molecule-sms
    number_capabilities:
      - SMS
    number_type: LONG_CODE
    tags:
      Environment: molecule

- name: Request a simulator phone number
  linuxhq.aws.pinpoint_sms_voice_phone_number:
    client_token: "{{ simulator_request_token }}"
    iso_country_code: US
    message_type: TRANSACTIONAL
    name: molecule-simulator
    number_capabilities:
      - SMS
    number_type: SIMULATOR

- name: Ensure a phone number is absent
  linuxhq.aws.pinpoint_sms_voice_phone_number:
    name: molecule-sms
    state: absent

- name: Ensure a specific phone number is absent
  linuxhq.aws.pinpoint_sms_voice_phone_number:
    name: molecule-sms
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
    messaging_limits:
      description:
        - The messaging limits that apply to the phone number.
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
    pricing_tier:
      description: The pricing model of the phone number.
      returned: when returned by AWS
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
      returned: when O(state=present)
      type: dict
    two_way_channel_arn:
      description: The ARN of the two-way channel that receives incoming messages.
      returned: when returned by AWS
      type: str
    two_way_channel_role:
      description: The ARN of the IAM role a service assumes to post incoming messages.
      returned: when returned by AWS
      type: str
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
    is_replayed_deleted_resource,
    last_phone_number_message,
    list_pool_origination_identities,
    list_tags,
    pool_is_deleting,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    require_no_reserved_tag_keys,
    require_resulting_tag_limit,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.validation import require_non_blank
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    sleep_until_next_poll,
    wait_deadline,
)

# Settings AWS gives a requested number when the request omits them, used only to predict check-mode results.
REQUEST_CREATION_DEFAULTS = {"DeletionProtectionEnabled": False, "InternationalSendingEnabled": False}
# Settings a number shares with its pool, which AWS gives these values only for a number requested outside a pool.
UNPOOLED_CREATION_DEFAULTS = {"OptOutListName": "Default", "SelfManagedOptOutsEnabled": False, "TwoWayEnabled": False}

SETTING_OPTIONS = {
    "DeletionProtectionEnabled": "deletion_protection_enabled",
    "InternationalSendingEnabled": "international_sending_enabled",
    "OptOutListName": "opt_out_list_name",
}


def phone_number_tags(client, module, phone_number, changed=False, missing_ok=False):
    """List tags; changed reports whether the phone number was already modified, for failure results.

    With missing_ok, a phone number released since it was described returns None instead of failing.
    """
    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"list_tags_for_resource": ("ResourceArn",)},
        changed=changed,
    )
    tags = list_tags(
        client, module, phone_number["PhoneNumberArn"], "phone number", changed=changed, missing_ok=missing_ok
    )
    if tags is None:
        return None

    return boto3_tag_list_to_ansible_dict(tags)


def find_phone_number_by_name(client, module, phone_numbers):
    """Return the number, with its tags, whose Name tag equals name; fail when several numbers have it."""
    matches = []
    for phone_number in phone_numbers:
        if phone_number.get("Status") == "DELETED":
            continue

        # Another actor can release a candidate between DescribePhoneNumbers and ListTagsForResource.
        tags = phone_number_tags(client, module, phone_number, missing_ok=True)
        if tags is not None and tags.get("Name") == module.params["name"]:
            matches.append(dict(phone_number, Tags=ansible_dict_to_boto3_tag_list(tags)))

    if len(matches) > 1:
        module.fail_json(
            msg=(
                f"Multiple Pinpoint SMS Voice V2 phone numbers matched name {module.params['name']}: "
                + ", ".join(sorted(phone_number["PhoneNumberId"] for phone_number in matches))
            )
        )

    return matches[0] if matches else None


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

    phone_numbers = response.get("PhoneNumbers", [])
    return phone_numbers[0] if phone_numbers else None


def wait_for_phone_number_active(client, module, phone_number_id, tags=None, changed=False):
    """Wait for a phone number; changed reports whether it was already modified, for failure results."""
    deadline = wait_deadline(module)
    phone_number = {}
    seen = False

    while time.monotonic() < deadline:
        found_phone_number = get_phone_number(client, module, phone_number_id, changed=changed)
        if found_phone_number is None and module.params.get("state") == "absent":
            return {}

        # A number missing before it is first seen may not be visible yet, so only a later absence is a release.
        if found_phone_number is None and seen:
            module.fail_json(
                changed=changed,
                msg=(
                    f"AWS End User Messaging SMS phone number {phone_number_id} "
                    "was released while waiting for it to become active"
                ),
                phone_number_id=phone_number_id,
            )

        seen = seen or found_phone_number is not None
        phone_number = found_phone_number or {}
        status = phone_number.get("Status")

        if status == "ACTIVE":
            if module.params.get("state") == "present":
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

        sleep_until_next_poll(module, deadline)

    module.fail_json(
        changed=changed,
        msg=f"Timed out waiting for AWS End User Messaging SMS phone number {phone_number_id} to become active",
        phone_number=boto3_resource_to_ansible_dict(phone_number, transform_tags=False, force_tags=False),
        phone_number_id=phone_number_id,
        status=phone_number.get("Status"),
    )


def updatable_settings_delta(module, current):
    updates = {}
    for field, option in SETTING_OPTIONS.items():
        desired = module.params[option]
        if desired is None:
            continue

        # OptOutListName accepts a name or ARN; DescribePhoneNumbers returns the name.
        if current.get(field) != (desired.rsplit("/", 1)[-1] if field == "OptOutListName" else desired):
            updates[field] = desired

    return updates


def phone_number_changes(client, module, current, tags):
    """Return the number with its tags and the settings and tag changes it needs."""
    updates = updatable_settings_delta(module, current)

    # Tags are read before any write, so tagging failures before any change report changed=False.
    current = dict(current)
    if "Tags" not in current:
        current["Tags"] = ansible_dict_to_boto3_tag_list(phone_number_tags(client, module, current))

    current_tags = boto3_tag_list_to_ansible_dict(current["Tags"])
    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        current_tags,
        tags,
        purge_tags=module.params["purge_tags"] if module.params["tags"] is not None else False,
    )
    # Live: SMS Voice V2 rejects these keys, after any settings update or tag removal of the same run.
    require_no_reserved_tag_keys(module, tags_to_set)
    require_resulting_tag_limit(
        module, current_tags, tags_to_set, tag_keys_to_unset, 200, "Pinpoint SMS Voice V2 phone number"
    )

    return current, updates, tags_to_set, tag_keys_to_unset


def update_phone_number(client, module, current, updates):
    phone_number_id = current["PhoneNumberId"]
    try:
        # A shared number must be addressed by the ARN the caller gave.
        response = client.update_phone_number(
            PhoneNumberId=module.params["phone_number_id"] or phone_number_id,
            **updates,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to update Pinpoint SMS Voice V2 phone number {phone_number_id}")

    response.pop("ResponseMetadata", None)
    return dict(current, **response)


def disassociate_failure_message(phone_number_id, pool_id):
    return f"Unable to disassociate Pinpoint SMS Voice V2 phone number {phone_number_id} from pool {pool_id}"


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
    response = list_pool_origination_identities(client, module, pool_id, missing_ok=True)
    if response is None:
        return

    originations = response.get("OriginationIdentities", [])

    identities = (phone_number_id, current["PhoneNumberArn"])
    # Deleting a pool disassociates its numbers, so the number can be released once its pool is going away.
    if is_last_phone_number(originations, identities) and not pool_is_deleting(client, module, pool_id):
        module.fail_json(changed=False, msg=last_phone_number_message(phone_number_id, pool_id))


def ensure_absent(client, module):
    phone_number_id = module.params["phone_number_id"]
    if phone_number_id:
        current = get_phone_number(client, module, phone_number_id)
    else:
        phone_numbers = query_list(
            module,
            client,
            "describe_phone_numbers",
            "PhoneNumbers",
            "Unable to describe Pinpoint SMS Voice V2 phone numbers",
            Owner="SELF",
        )
        current = find_phone_number_by_name(client, module, phone_numbers)
        if current is not None:
            phone_number_id = current["PhoneNumberId"]

    if current is not None and current.get("Status") == "DELETED":
        current = None

    changed = current is not None
    response = current

    # Only the pool module deletes pools, so a pool's only origination identity is never released here.
    if changed and module.check_mode and current.get("PoolId"):
        require_not_last_pool_phone_number(client, module, current)

    if changed and module.check_mode:
        # A real run returns the ReleasePhoneNumber response, which reports the number DELETED, and botocore drops
        # the members its model lacks, so keep only the described fields that response models.
        released_fields = client.meta.service_model.shape_for("ReleasePhoneNumberResult").members
        response = {key: value for key, value in current.items() if key in released_fields}
        response["Status"] = "DELETED"

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
        # Older botocore requires IsoCountryCode to disassociate; DescribePhoneNumbers always returns the country.
        disassociate_request = scrub_none_parameters(
            {
                "IsoCountryCode": current.get("IsoCountryCode"),
                "OriginationIdentity": phone_number_id,
                "PoolId": current.get("PoolId"),
            }
        )
        if current.get("PoolId"):
            methods["disassociate_origination_identity"] = tuple(disassociate_request)

        if current.get("DeletionProtectionEnabled"):
            methods["update_phone_number"] = ("DeletionProtectionEnabled", "PhoneNumberId")

        require_client_methods(module, client, "Pinpoint SMS Voice V2", methods)

        # Failures after the first successful change report changed=True.
        mutated = False
        if current.get("PoolId"):
            try:
                client.disassociate_origination_identity(
                    **disassociate_request,
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
                client.update_phone_number(
                    PhoneNumberId=phone_number_id,
                    DeletionProtectionEnabled=False,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                # Released elsewhere; only an earlier write by this run is a change.
                exit_result(module, mutated, None)
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
            wait_for_phone_number_active(client, module, phone_number_id, changed=True)

        try:
            response = client.release_phone_number(
                PhoneNumberId=phone_number_id,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            # Released elsewhere; only an earlier write by this run is a change.
            changed = mutated
            response = None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                changed=mutated,
                msg=f"Unable to release Pinpoint SMS Voice V2 phone number {phone_number_id}",
            )

        if response is not None:
            response.pop("ResponseMetadata", None)

    exit_result(module, changed, response)


def ensure_present(client, module, tags):
    """Converge the phone number; tags are the validated tags with the Name tag from name."""
    deletion_protection_enabled = module.params["deletion_protection_enabled"]
    iso_country_code = module.params["iso_country_code"]
    message_type = module.params["message_type"]
    number_capabilities = module.params["number_capabilities"]
    number_type = module.params["number_type"]
    opt_out_list_name = module.params["opt_out_list_name"]
    pool_id = module.params["pool_id"]
    registration_id = module.params["registration_id"]
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

    # Match the attributes fixed by RequestPhoneNumber and the current pool; updatable settings converge below.
    desired = {
        "IsoCountryCode": iso_country_code,
        "MessageType": message_type,
        "NumberCapabilities": sorted(set(number_capabilities)),
        "NumberType": number_type,
    }
    if pool_id is not None:
        desired["PoolId"] = pool_id.rsplit("/", 1)[-1]

    # RequestPhoneNumber accepts an ID or an ARN, but DescribePhoneNumbers returns the ID.
    if registration_id is not None:
        desired["RegistrationId"] = registration_id.rsplit("/", 1)[-1]

    matches = [
        phone_number
        for phone_number in phone_numbers
        if phone_number.get("Status") != "DELETED"
        and all(
            (sorted(set(phone_number[key])) if key == "NumberCapabilities" else phone_number.get(key)) == value
            for key, value in desired.items()
        )
    ]
    if module.params["phone_number_id"]:
        current = matches[0] if matches else None
    else:
        # Without phone_number_id, the Name tag identifies the number; other tags converge below.
        current = find_phone_number_by_name(client, module, matches)

    if current is not None:
        current, updates, tags_to_set, tag_keys_to_unset = phone_number_changes(client, module, current, tags)
        if current.get("Status") != "ACTIVE" and (wait or updates or tags_to_set or tag_keys_to_unset):
            if module.check_mode:
                # A real run first waits for the number to become ACTIVE.
                current = dict(current, Status="ACTIVE")
            else:
                # Changes always wait for ACTIVE, even when wait=false, and are recalculated from the settled number.
                current = wait_for_phone_number_active(
                    client,
                    module,
                    module.params["phone_number_id"] or current["PhoneNumberId"],
                    tags=current.get("Tags"),
                )
                current, updates, tags_to_set, tag_keys_to_unset = phone_number_changes(client, module, current, tags)

        if updates and current.get("PoolId"):
            options = ", ".join(SETTING_OPTIONS[field] for field in updates)
            module.fail_json(
                msg=f"Unable to update {options} for Pinpoint SMS Voice V2 phone number {current['PhoneNumberId']} in pool {current['PoolId']}"
            )

        tags_changed = bool(tags_to_set or tag_keys_to_unset)
        # Check mode checks the SDK as the real run does, so it fails where the real run fails before any write.
        methods = {}
        if updates:
            methods["update_phone_number"] = ("PhoneNumberId",) + tuple(updates)

        if tags_to_set:
            methods["tag_resource"] = ("ResourceArn", "Tags")

        if tag_keys_to_unset:
            methods["untag_resource"] = ("ResourceArn", "TagKeys")

        if methods:
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
            "tags": sorted(ansible_dict_to_boto3_tag_list(tags), key=lambda tag: tag["Key"]),
        }
    )
    request = snake_dict_to_camel_dict(parameters, capitalize_first=True)
    # Check mode checks the SDK as the real run does, so it fails where the real run fails before any write.
    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"request_phone_number": tuple(request)},
    )

    if module.check_mode:
        # A real run returns the waited DescribePhoneNumbers item or the RequestPhoneNumber response, and botocore
        # drops the members its model lacks, so predict only the defaults that response returns.
        modeled_fields = client.meta.service_model.shape_for(
            "PhoneNumberInformation" if wait else "RequestPhoneNumberResult"
        ).members
        defaults = dict(REQUEST_CREATION_DEFAULTS, **({} if pool_id else UNPOOLED_CREATION_DEFAULTS))
        predicted = {field: value for field, value in defaults.items() if field in modeled_fields}
        predicted.update(request)
        predicted.pop("ClientToken", None)
        # A real run returns ACTIVE after the wait; without it, the PENDING status RequestPhoneNumber returns.
        predicted["Status"] = "ACTIVE" if wait else "PENDING"
        # Project IDs and names as DescribePhoneNumbers returns them, rather than the ARNs requested.
        for field in ("OptOutListName", "PoolId", "RegistrationId"):
            if field in predicted:
                predicted[field] = predicted[field].rsplit("/", 1)[-1]

        exit_result(module, True, predicted)

    try:
        response = client.request_phone_number(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Unable to request Pinpoint SMS Voice V2 phone number")

    response.pop("ResponseMetadata", None)

    if module.params["client_token"] is not None and is_replayed_deleted_resource(
        lambda: get_phone_number(client, module, response["PhoneNumberId"], changed=True), "DELETED"
    ):
        # Live: a token reused after a release returns the released number, which DescribePhoneNumbers no longer has.
        module.fail_json(
            msg=(
                f"client_token {module.params['client_token']} was already used to request AWS End User "
                f"Messaging SMS phone number {response['PhoneNumberId']}, which has since been released; "
                "use a new client_token or omit it"
            ),
            phone_number_id=response["PhoneNumberId"],
        )

    if module.params["client_token"] is not None and response["PhoneNumberId"] in {
        phone_number["PhoneNumberId"] for phone_number in phone_numbers
    }:
        # Live: a reused token returns the number the earlier request returned without requesting another, even when
        # that number no longer matches; it was described before the request and did not match.
        module.fail_json(
            msg=(
                f"client_token {module.params['client_token']} was already used to request AWS End User "
                f"Messaging SMS phone number {response['PhoneNumberId']}, which no longer matches the requested "
                "attributes, pool, or Name tag; use a new client_token or omit it, or set phone_number_id to manage "
                "that number"
            ),
            phone_number_id=response["PhoneNumberId"],
        )

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
        "name": {"required": True, "type": "str"},
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
        ],
        supports_check_mode=True,
    )

    state = module.params["state"]

    if state == "present":
        # required_if counts only supplied keys, so an explicit null passes it. A null for an option with choices,
        # such as number_capabilities, already fails the choices check.
        if module.params["iso_country_code"] is None:
            module.fail_json(msg="state is present but all of the following are missing: iso_country_code")

        if not re.fullmatch(r"[A-Z]{2}", module.params["iso_country_code"]):
            module.fail_json(msg="iso_country_code must be exactly two uppercase letters")

        if module.params["number_type"] == "SIMULATOR" and module.params["message_type"] != "TRANSACTIONAL":
            module.fail_json(msg="message_type must be TRANSACTIONAL when number_type is SIMULATOR")

        # AWS rejects empty identifiers, which check mode would otherwise predict as a new request or an update.
        for option in ("opt_out_list_name", "pool_id", "registration_id"):
            require_non_blank(module, module.params[option], option)

        # name replaces any Name entry in tags, so only the tags sent to AWS are checked.
        tags = dict(module.params["tags"] or {}, Name=module.params["name"])
        require_valid_tags(module, tags, 200, restricted_characters=True)

    require_positive_wait_bounds(module, always=True)

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())
    # Waits and re-reads describe by PhoneNumberIds on every path.
    describe_parameters = ("MaxResults", "NextToken", "PhoneNumberIds")
    if not module.params["phone_number_id"]:
        describe_parameters += ("Filters", "Owner") if state == "present" else ("Owner",)

    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {"describe_phone_numbers": describe_parameters},
    )

    if state == "present":
        ensure_present(client, module, tags)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
