#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_pool
short_description: Manage aws end user messaging sms phone pools
description:
  - Manages AWS End User Messaging SMS phone pools.
  - This module maps to the Pinpoint SMS Voice V2 C(CreatePool) API,
    the API behind C(aws pinpoint-sms-voice-v2 create-pool).
author:
  - Taylor Kimball (@tkimball83)
options:
  client_token:
    description:
      - Unique idempotency token for the pool request.
      - When omitted, AWS generates an idempotency token for the request.
    type: str
  deletion_protection_enabled:
    default: false
    description:
      - Whether deletion protection is enabled for the pool.
    type: bool
  iso_country_code:
    description:
      - The two-character ISO 3166-1 alpha-2 country or region code.
      - When provided, this must be exactly two uppercase letters.
      - This field is optional for origination identities that are not
        country-specific.
    type: str
  message_type:
    description:
      - The type of messages sent from the pool.
      - This is required when O(state=present).
      - This option is ignored when O(state=absent).
    choices:
      - PROMOTIONAL
      - TRANSACTIONAL
    type: str
  name:
    description:
      - Name of the phone pool.
      - This is used as the C(Name) tag.
      - This is required when O(state=present).
    type: str
  origination_identity:
    description:
      - The origination identity to associate with the pool.
      - This can be a phone number ID, phone number ARN, sender ID, or sender
        ID ARN.
      - This is required when O(state=present).
      - This option is ignored when O(state=absent).
    type: str
  pool_id:
    description:
      - The pool ID or ARN.
      - This is required when O(state=absent).
      - When set with O(state=present), this pool is managed directly instead
        of searching by O(origination_identity).
      - When set with O(state=present), the pool must already exist.
    type: str
  purge_tags:
    default: true
    description:
      - Whether tags not listed in the desired tag set should be removed.
      - This option is only applied when O(tags) is provided.
    type: bool
  state:
    choices:
      - absent
      - present
    default: present
    description:
      - Whether the phone pool should exist.
    type: str
  tags:
    description:
      - Tags to apply to the pool.
      - This must contain at most 200 entries; keys must contain 1 to 128 characters and values at most 256 characters.
    type: dict
  wait:
    default: true
    description:
      - Whether to wait for the phone pool status to become C(ACTIVE).
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
- name: Ensure a transactional SMS phone pool is present
  linuxhq.aws.pinpoint_sms_voice_phone_pool:
    iso_country_code: US
    message_type: TRANSACTIONAL
    name: molecule-pool
    origination_identity: phone-0123456789abcdef0123456789abcdef
    tags:
      Environment: molecule

- name: Ensure a phone pool is absent
  linuxhq.aws.pinpoint_sms_voice_phone_pool:
    pool_id: pool-0123456789abcdef0123456789abcdef
    state: absent
"""

RETURN = r"""
pool:
  description:
    - The phone pool.
    - C(origination_identities) and C(tags) are gathered by the module and
      included when available.
  returned: when available
  type: dict
pool_arn:
  description:
    - The ARN of the phone pool.
  returned: when available
  type: str
pool_id:
  description:
    - The ID of the phone pool.
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
)


def describe_pools(client, module, **request):
    try:
        response = paginated_query_with_retries(
            client,
            "describe_pools",
            **scrub_none_parameters(request),
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return []
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Unable to describe Pinpoint SMS Voice V2 pools")

    pools = response.get("Pools") if isinstance(response, dict) else None
    if not isinstance(pools, list):
        module.fail_json(msg="AWS returned malformed Pinpoint SMS Voice V2 pool data")

    for pool in pools:
        validate_pool(module, pool, "describing pools")

    return pools


def validate_pool(module, pool, context):
    if (
        not isinstance(pool, dict)
        or not isinstance(pool.get("PoolId"), str)
        or not isinstance(pool.get("Status"), str)
        or ("PoolArn" in pool and not isinstance(pool["PoolArn"], str))
        or ("DeletionProtectionEnabled" in pool and not isinstance(pool["DeletionProtectionEnabled"], bool))
        or ("MessageType" in pool and not isinstance(pool["MessageType"], str))
    ):
        module.fail_json(msg=f"AWS returned a malformed Pinpoint SMS Voice V2 pool while {context}")

    return pool


def pool_with_origination_identities(client, module, pool):
    pool = dict(pool)
    pool_id = pool.get("PoolId")

    if pool_id:
        pool["OriginationIdentities"] = query_list(
            module,
            client,
            "list_pool_origination_identities",
            "OriginationIdentities",
            "Unable to list origination identities for Pinpoint SMS Voice " f"V2 pool {pool_id}",
            PoolId=pool_id,
        )
        if any(
            not isinstance(identity, dict)
            or not any(isinstance(identity.get(key), str) for key in ("OriginationIdentity", "OriginationIdentityArn"))
            for identity in pool["OriginationIdentities"]
        ):
            module.fail_json(
                msg=f"AWS returned malformed origination identities for Pinpoint SMS Voice V2 pool {pool_id}"
            )

    else:
        pool["OriginationIdentities"] = []

    return pool


def pool_with_tags(client, module, pool):
    pool = dict(pool)
    arn = pool.get("PoolArn")
    tags = {}

    if arn:
        try:
            response = client.list_tags_for_resource(
                ResourceArn=arn,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 pool {arn}")

        tag_list = response.get("Tags", []) if isinstance(response, dict) else None
        if not isinstance(tag_list, list) or any(
            not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str)
            for tag in tag_list
        ):
            module.fail_json(msg=f"AWS returned malformed tags for Pinpoint SMS Voice V2 pool {arn}")

        tags = boto3_tag_list_to_ansible_dict(tag_list)

    pool["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return pool


def select_pool_by_id(module, pools, pool_id):
    if not pools:
        return None

    expected_pool_id = pool_id.rsplit("/", 1)[-1]
    if pools[0]["PoolId"] != expected_pool_id:
        module.fail_json(msg=f"AWS returned the wrong Pinpoint SMS Voice V2 pool while describing {pool_id}")

    return pools[0]


def get_pool_by_id(client, module, pool_id):
    pools = describe_pools(client, module, PoolIds=[pool_id])
    pool = select_pool_by_id(module, pools, pool_id)
    if pool is None:
        return None

    pool = pool_with_origination_identities(client, module, pool)

    return pool_with_tags(client, module, pool)


def wait_for_pool_active(client, module, pool_id):
    deadline = time.monotonic() + module.params["wait_timeout"]
    pool = {}

    while time.monotonic() < deadline:
        pools = describe_pools(client, module, PoolIds=[pool_id])
        pool = select_pool_by_id(module, pools, pool_id)
        if pool is None and module.params.get("state") == "absent":
            return {}

        pool = pool or {}
        status = pool.get("Status")

        if status == "ACTIVE":
            return pool

        if status == "DELETING":
            if module.params.get("state") == "absent":
                return pool

            module.fail_json(
                msg=("AWS End User Messaging SMS phone pool " f"{pool_id} was deleted before becoming active"),
                pool=boto3_resource_to_ansible_dict(pool, transform_tags=False, force_tags=False),
                pool_id=pool_id,
                status=status,
            )

        time.sleep(
            min(
                module.params["wait_delay"],
                max(0, deadline - time.monotonic()),
            )
        )

    module.fail_json(
        msg=("Timed out waiting for AWS End User Messaging SMS phone pool " f"{pool_id} to become active"),
        pool=boto3_resource_to_ansible_dict(pool, transform_tags=False, force_tags=False),
        pool_id=pool_id,
        status=pool.get("Status"),
    )


def find_pool(client, module):
    if module.params["pool_id"] is not None:
        return get_pool_by_id(client, module, module.params["pool_id"])

    filters = ansible_dict_to_boto3_filter_list({"message-type": module.params["message_type"]})
    iso_country_code = module.params["iso_country_code"]
    matches = []

    for pool in describe_pools(client, module, Filters=filters, Owner="SELF"):
        if pool.get("Status") == "DELETING":
            continue

        pool = pool_with_origination_identities(client, module, pool)

        for origination in pool.get("OriginationIdentities", []):
            if module.params["origination_identity"] not in (
                origination.get("OriginationIdentity"),
                origination.get("OriginationIdentityArn"),
            ):
                continue

            if iso_country_code is not None and origination.get("IsoCountryCode") != iso_country_code:
                continue

            pool = pool_with_tags(client, module, pool)
            if boto3_tag_list_to_ansible_dict(pool.get("Tags", [])).get("Name") == module.params["name"]:
                matches.append(pool)
                break

    if len(matches) > 1:
        module.fail_json(
            msg=(
                f"Multiple Pinpoint SMS Voice V2 pools matched name "
                f"{module.params['name']}: " + ", ".join(sorted(pool.get("PoolId", "") for pool in matches))
            )
        )

    return matches[0] if matches else None


def exit_result(module, changed, pool):
    normalized_pool = boto3_resource_to_ansible_dict(pool or {}, transform_tags=True, force_tags=False)
    result = {
        "changed": changed,
        "state": module.params["state"],
    }
    if normalized_pool:
        result["pool"] = normalized_pool

    if normalized_pool.get("pool_arn"):
        result["pool_arn"] = normalized_pool["pool_arn"]

    if normalized_pool.get("pool_id"):
        result["pool_id"] = normalized_pool["pool_id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    pool_id = module.params["pool_id"]
    pools = describe_pools(client, module, PoolIds=[pool_id])
    current = select_pool_by_id(module, pools, pool_id)

    if current is not None and current.get("Status") == "DELETING":
        current = None

    changed = current is not None
    response = current

    if changed and not module.check_mode:
        if current.get("Status") != "ACTIVE":
            current = wait_for_pool_active(client, module, pool_id)
            if current.get("Status") == "DELETING":
                exit_result(module, True, current)

        if current.get("DeletionProtectionEnabled"):
            try:
                current = client.update_pool(
                    PoolId=pool_id,
                    DeletionProtectionEnabled=False,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                exit_result(module, True, None)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=("Unable to disable deletion protection for Pinpoint " f"SMS Voice V2 pool {pool_id}"),
                )

            validate_pool(module, current, "disabling deletion protection")

        if current.get("Status") != "ACTIVE" or current.get("DeletionProtectionEnabled"):
            current = wait_for_pool_active(client, module, pool_id)
            if current.get("Status") == "DELETING":
                exit_result(module, True, current)

        try:
            response = client.delete_pool(
                PoolId=pool_id,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            response = None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to delete Pinpoint SMS Voice V2 pool {pool_id}")

        if response is not None:
            validate_pool(module, response, "deleting a pool")
            response.pop("ResponseMetadata", None)

    exit_result(module, changed, response)


def ensure_present(client, module):
    deletion_protection_enabled = module.params["deletion_protection_enabled"]
    message_type = module.params["message_type"]
    wait = module.params["wait"]
    current = find_pool(client, module)
    if current is None and module.params.get("pool_id") is not None:
        module.fail_json(msg=("Pinpoint SMS Voice V2 pool " f"{module.params['pool_id']} does not exist"))

    if current is not None and current.get("MessageType") != message_type:
        module.fail_json(
            msg=("Cannot modify message_type for existing Pinpoint SMS Voice V2 " f"pool {current.get('PoolId')}")
        )

    if (
        wait
        and not module.check_mode
        and current is not None
        and current.get("Status") != "ACTIVE"
        and current.get("PoolId")
    ):
        wait_for_pool_active(client, module, current["PoolId"])
        current = get_pool_by_id(client, module, current["PoolId"]) or current

    update_request = {}
    if current is not None and current.get("DeletionProtectionEnabled") != deletion_protection_enabled:
        update_request["DeletionProtectionEnabled"] = deletion_protection_enabled

    user_tags = module.params["tags"]
    tags = dict(user_tags or {})
    tags["Name"] = module.params["name"]

    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
        tags,
        purge_tags=module.params["purge_tags"] if user_tags is not None else False,
    )

    changed = current is None or bool(update_request or tags_to_set or tag_keys_to_unset)

    if (
        changed
        and not module.check_mode
        and current is not None
        and current.get("Status") != "ACTIVE"
        and current.get("PoolId")
    ):
        wait_for_pool_active(client, module, current["PoolId"])
        current = get_pool_by_id(client, module, current["PoolId"]) or current
        update_request = {}
        if current.get("DeletionProtectionEnabled") != deletion_protection_enabled:
            update_request["DeletionProtectionEnabled"] = deletion_protection_enabled

        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
            tags,
            purge_tags=(module.params["purge_tags"] if user_tags is not None else False),
        )
        changed = bool(update_request or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        pool_changed = current is None or bool(update_request)
        if current is None:
            parameters = scrub_none_parameters(
                {
                    "client_token": module.params["client_token"],
                    "deletion_protection_enabled": deletion_protection_enabled,
                    "iso_country_code": module.params["iso_country_code"],
                    "message_type": message_type,
                    "origination_identity": module.params["origination_identity"],
                    "tags": sorted(
                        ansible_dict_to_boto3_tag_list(tags),
                        key=lambda tag: tag["Key"],
                    ),
                }
            )
            request = snake_dict_to_camel_dict(parameters, capitalize_first=True)

            try:
                current = client.create_pool(**request, aws_retry=True)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg="Unable to create Pinpoint SMS Voice V2 pool")

            validate_pool(module, current, "creating a pool")
            current.pop("ResponseMetadata", None)
            current["OriginationIdentities"] = [
                scrub_none_parameters(
                    {
                        "OriginationIdentity": module.params["origination_identity"],
                        "IsoCountryCode": module.params["iso_country_code"],
                    }
                )
            ]
            current["Tags"] = request["Tags"]
            tags_to_set, tag_keys_to_unset = ({}, [])
        else:
            if update_request:
                previous = current
                try:
                    current = client.update_pool(
                        PoolId=current["PoolId"],
                        **update_request,
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=("Unable to update Pinpoint SMS Voice V2 pool " f"{current['PoolId']}"),
                    )

                validate_pool(module, current, "updating a pool")
                current.pop("ResponseMetadata", None)
                current["OriginationIdentities"] = previous.get("OriginationIdentities", [])
                current["Tags"] = previous.get("Tags", [])

                if (tags_to_set or tag_keys_to_unset) and current.get("Status") != "ACTIVE":
                    active = wait_for_pool_active(client, module, current["PoolId"])
                    active["OriginationIdentities"] = current["OriginationIdentities"]
                    active["Tags"] = current["Tags"]
                    current = active

            arn = current.get("PoolArn")

            if (tags_to_set or tag_keys_to_unset) and not arn:
                module.fail_json(msg="Unable to tag Pinpoint SMS Voice V2 pool")

            reconcile_arn_tags(
                module,
                client,
                arn,
                tags_to_set,
                tag_keys_to_unset,
                "Pinpoint SMS Voice V2 pool",
            )

            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

        if wait and pool_changed and current.get("PoolId"):
            if current.get("Status") != "ACTIVE":
                wait_for_pool_active(client, module, current["PoolId"])

            current = get_pool_by_id(client, module, current["PoolId"]) or current
    elif changed and module.check_mode:
        new_pool = current is None
        current = dict(current or {})
        current.update(
            {
                "DeletionProtectionEnabled": deletion_protection_enabled,
                "MessageType": message_type,
                "Status": current.get("Status") or "ACTIVE",
            }
        )
        if new_pool:
            current["OriginationIdentities"] = [
                scrub_none_parameters(
                    {
                        "OriginationIdentity": module.params["origination_identity"],
                        "IsoCountryCode": module.params["iso_country_code"],
                    }
                )
            ]

        current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

    exit_result(module, changed, current)


def main():
    argument_spec = {
        "client_token": {"no_log": False, "type": "str"},
        "deletion_protection_enabled": {"default": False, "type": "bool"},
        "iso_country_code": {"type": "str"},
        "message_type": {
            "choices": ["PROMOTIONAL", "TRANSACTIONAL"],
            "type": "str",
        },
        "name": {"type": "str"},
        "origination_identity": {"type": "str"},
        "pool_id": {"type": "str"},
        "purge_tags": {"default": True, "type": "bool"},
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
            ("state", "present", ["message_type", "name", "origination_identity"]),
            ("state", "absent", ["pool_id"]),
        ],
        supports_check_mode=True,
    )
    state = module.params["state"]

    if state == "present":
        iso_country_code = module.params["iso_country_code"]

        if iso_country_code is not None and not re.fullmatch(r"[A-Z]{2}", iso_country_code):
            module.fail_json(msg="iso_country_code must be exactly two uppercase letters")

    require_valid_tags(module, module.params["tags"] if state == "present" else None, 200)
    if state == "present":
        tags = dict(module.params["tags"] or {})
        tags["Name"] = module.params["name"]
        require_valid_tags(module, tags, 200)

    require_positive_wait_bounds(module, always=True)

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())
    describe_parameters = (
        ("PoolIds",) if state == "absent" or module.params["pool_id"] is not None else ("Filters", "Owner")
    ) + ("MaxResults", "NextToken")
    methods = {"describe_pools": describe_parameters}
    if state == "present":
        create_parameters = (
            "DeletionProtectionEnabled",
            "MessageType",
            "OriginationIdentity",
            "Tags",
        )
        if module.params["client_token"] is not None:
            create_parameters += ("ClientToken",)

        if module.params["iso_country_code"] is not None:
            create_parameters += ("IsoCountryCode",)

        methods["create_pool"] = create_parameters
        methods["list_pool_origination_identities"] = (
            "PoolId",
            "MaxResults",
            "NextToken",
        )
        methods["list_tags_for_resource"] = ("ResourceArn",)
        if module.params["pool_id"] is not None or module.params["tags"] is not None:
            methods["tag_resource"] = ("ResourceArn", "Tags")

        methods["update_pool"] = ("DeletionProtectionEnabled", "PoolId")
        if module.params["tags"] is not None and module.params["purge_tags"]:
            methods["untag_resource"] = ("ResourceArn", "TagKeys")

    if state == "absent":
        methods["delete_pool"] = ("PoolId",)
        methods["update_pool"] = ("DeletionProtectionEnabled", "PoolId")

    require_client_methods(module, client, "Pinpoint SMS Voice V2", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
