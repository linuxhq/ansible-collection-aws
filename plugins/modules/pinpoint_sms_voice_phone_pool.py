#!/usr/bin/python
# Copyright: Taylor Kimball
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
    type: str
  purge_tags:
    default: true
    description:
      - Whether tags not listed in the desired tag set should be removed.
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
- name: Ensure a transactional SMS phone pool is present
  linuxhq.aws.pinpoint_sms_voice_phone_pool:
    name: molecule-pool
    origination_identity: phone-0123456789abcdef0123456789abcdef
    iso_country_code: US
    message_type: TRANSACTIONAL
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

import time

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


def sorted_tag_list(tags):
    return sorted(ansible_dict_to_boto3_tag_list(tags), key=lambda tag: tag["Key"])


def desired_tags(module):
    tags = dict(module.params["tags"] or {})
    if module.params["name"] is not None:
        tags["Name"] = module.params["name"]
    return tags or None


def create_pool_parameters(module):
    tags = desired_tags(module)
    return scrub_none_parameters(
        {
            "client_token": module.params["client_token"],
            "deletion_protection_enabled": module.params["deletion_protection_enabled"],
            "iso_country_code": module.params["iso_country_code"],
            "message_type": module.params["message_type"],
            "origination_identity": module.params["origination_identity"],
            "tags": sorted_tag_list(tags) if tags is not None else None,
        }
    )


def create_pool_request(client, module):
    parameters = create_pool_parameters(module)
    request = snake_dict_to_camel_dict(parameters, capitalize_first=True)
    supported_parameters = set(
        client.meta.service_model.operation_model("CreatePool").input_shape.members
    )
    unsupported_parameters = sorted(set(request) - supported_parameters)
    if unsupported_parameters:
        module.fail_json(
            msg=(
                "Installed botocore does not support Pinpoint SMS Voice V2 "
                "CreatePool parameter(s): "
                f"{', '.join(unsupported_parameters)}"
            )
        )
    return request


def validate_present(module):
    if module.params["message_type"] not in ("PROMOTIONAL", "TRANSACTIONAL"):
        module.fail_json(msg="message_type must be one of PROMOTIONAL, TRANSACTIONAL")


def describe_pools(client, module, **request):
    try:
        return paginated_query_with_retries(
            client,
            "describe_pools",
            **scrub_none_parameters(request),
        ).get("Pools", [])
    except is_boto3_error_code("ResourceNotFoundException"):
        return []
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe Pinpoint SMS Voice V2 pools")


def pool_tags(client, module, pool):
    arn = pool.get("PoolArn")
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
            e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 pool {arn}"
        )


def pool_originations(client, module, pool):
    pool_id = pool.get("PoolId")
    if not pool_id:
        return []
    try:
        return paginated_query_with_retries(
            client,
            "list_pool_origination_identities",
            PoolId=pool_id,
        ).get("OriginationIdentities", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list origination identities for Pinpoint SMS Voice "
                f"V2 pool {pool_id}"
            ),
        )


def enrich_pool(client, module, pool):
    if not pool:
        return None
    pool = dict(pool)
    pool["OriginationIdentities"] = pool_originations(client, module, pool)
    pool["Tags"] = ansible_dict_to_boto3_tag_list(pool_tags(client, module, pool))
    return pool


def get_pool_by_id(client, module, pool_id):
    pools = describe_pools(client, module, PoolIds=[pool_id])
    return enrich_pool(client, module, pools[0]) if pools else None


def get_pool_status(client, module, pool_id):
    pools = describe_pools(client, module, PoolIds=[pool_id])
    return pools[0] if pools else None


def wait_for_pool_active(client, module, pool_id):
    deadline = time.monotonic() + module.params["wait_timeout"]
    pool = {}

    while time.monotonic() < deadline:
        pool = get_pool_status(client, module, pool_id) or {}
        status = pool.get("Status")
        if status == "ACTIVE":
            return pool
        if status == "DELETING":
            module.fail_json(
                msg=(
                    "AWS End User Messaging SMS phone pool "
                    f"{pool_id} was deleted before becoming active"
                ),
                pool=boto3_resource_to_ansible_dict(
                    pool, transform_tags=False, force_tags=False
                ),
                pool_id=pool_id,
                status=status,
            )
        time.sleep(max(1, module.params["wait_delay"]))

    module.fail_json(
        msg=(
            "Timed out waiting for AWS End User Messaging SMS phone pool "
            f"{pool_id} to become active"
        ),
        pool=boto3_resource_to_ansible_dict(
            pool, transform_tags=False, force_tags=False
        ),
        pool_id=pool_id,
        status=pool.get("Status"),
    )


def origination_identity_matches(module, origination):
    desired_identity = module.params["origination_identity"]
    if desired_identity not in (
        origination.get("OriginationIdentity"),
        origination.get("OriginationIdentityArn"),
    ):
        return False
    if module.params["iso_country_code"] is not None:
        return origination.get("IsoCountryCode") == module.params["iso_country_code"]
    return True


def pool_matches_origination(module, pool):
    return any(
        origination_identity_matches(module, origination)
        for origination in pool.get("OriginationIdentities", [])
    )


def find_pool(client, module):
    if module.params["pool_id"] is not None:
        return get_pool_by_id(client, module, module.params["pool_id"])

    filters = ansible_dict_to_boto3_filter_list(
        {"message-type": module.params["message_type"]}
    )
    for pool in describe_pools(client, module, Filters=filters, Owner="SELF"):
        if pool.get("Status") == "DELETING":
            continue
        pool = enrich_pool(client, module, pool)
        if pool_matches_origination(module, pool):
            return pool
    return None


def pool_create_only_changed(module, pool):
    if pool is None:
        return False
    return pool.get("MessageType") != module.params["message_type"]


def pool_update_request(module, pool):
    request = {}
    if (
        pool.get("DeletionProtectionEnabled")
        != module.params["deletion_protection_enabled"]
    ):
        request["DeletionProtectionEnabled"] = module.params[
            "deletion_protection_enabled"
        ]
    return request


def apply_tag_changes(client, module, pool, tags_to_set, tag_keys_to_unset):
    arn = pool.get("PoolArn")
    if not arn:
        module.fail_json(msg="Unable to tag Pinpoint SMS Voice V2 pool")

    if tag_keys_to_unset:
        try:
            client.untag_resource(
                ResourceArn=arn,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to remove tags from Pinpoint SMS Voice V2 pool {arn}"
            )

    if tags_to_set:
        try:
            client.tag_resource(
                ResourceArn=arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to tag Pinpoint SMS Voice V2 pool {arn}"
            )


def update_pool(client, module, pool, request):
    if not request:
        return pool
    try:
        response = client.update_pool(
            PoolId=pool["PoolId"],
            **request,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to update Pinpoint SMS Voice V2 pool {pool['PoolId']}",
        )
    return response


def create_pool(client, module):
    try:
        return client.create_pool(
            **create_pool_request(client, module),
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to create Pinpoint SMS Voice V2 pool")


def delete_pool(client, module, pool_id):
    try:
        return client.delete_pool(
            PoolId=pool_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to delete Pinpoint SMS Voice V2 pool {pool_id}"
        )


def check_mode_pool(module, current=None):
    pool = dict(current or {})
    pool.update(
        {
            "DeletionProtectionEnabled": module.params["deletion_protection_enabled"],
            "MessageType": module.params["message_type"],
            "Status": pool.get("Status") or "ACTIVE",
        }
    )
    if module.params["origination_identity"] is not None:
        pool["OriginationIdentities"] = pool.get("OriginationIdentities") or [
            scrub_none_parameters(
                {
                    "OriginationIdentity": module.params["origination_identity"],
                    "IsoCountryCode": module.params["iso_country_code"],
                }
            )
        ]
    tags = desired_tags(module)
    if tags is not None:
        pool["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return pool


def pool_with_updated_tags(pool, tags_to_set, tag_keys_to_unset):
    pool = dict(pool)
    tags = boto3_tag_list_to_ansible_dict((pool or {}).get("Tags", []))
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)
    tags.update(tags_to_set)
    pool["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return pool


def exit_result(module, changed, pool, state):
    normalized_pool = boto3_resource_to_ansible_dict(
        pool or {}, transform_tags=True, force_tags=False
    )
    result = {
        "changed": changed,
        "pool": normalized_pool,
        "pool_arn": normalized_pool.get("pool_arn"),
        "pool_id": normalized_pool.get("pool_id"),
        "state": state,
    }
    result.update(normalized_pool)
    module.exit_json(**result)


def ensure_absent(client, module):
    current = get_pool_by_id(client, module, module.params["pool_id"])
    changed = current is not None
    response = current

    if changed and not module.check_mode:
        response = delete_pool(client, module, module.params["pool_id"])

    exit_result(module, changed, response or current, "absent")


def ensure_present(client, module):
    validate_present(module)
    current = find_pool(client, module)
    if current is not None and pool_create_only_changed(module, current):
        module.fail_json(
            msg=(
                "Cannot modify message_type for existing Pinpoint SMS Voice V2 "
                f"pool {current.get('PoolId')}"
            )
        )
    if (
        module.params["wait"]
        and current is not None
        and current.get("Status") != "ACTIVE"
        and current.get("PoolId")
    ):
        wait_for_pool_active(client, module, current["PoolId"])
        current = get_pool_by_id(client, module, current["PoolId"]) or current

    update_request = pool_update_request(module, current or {})
    tags = desired_tags(module)
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
            tags,
            purge_tags=module.params["purge_tags"],
        )
    changed = current is None or bool(
        update_request or tags_to_set or tag_keys_to_unset
    )

    if changed and not module.check_mode:
        pool_changed = current is None or bool(update_request)
        if current is None:
            current = create_pool(client, module)
        else:
            current = update_pool(client, module, current, update_request)
            apply_tag_changes(client, module, current, tags_to_set, tag_keys_to_unset)
            if not update_request:
                current = pool_with_updated_tags(
                    current, tags_to_set, tag_keys_to_unset
                )
        if (
            module.params["wait"]
            and current.get("Status") != "ACTIVE"
            and current.get("PoolId")
        ):
            wait_for_pool_active(client, module, current["PoolId"])
            pool_changed = True
        if pool_changed and current.get("PoolId"):
            current = get_pool_by_id(client, module, current["PoolId"]) or current
    elif changed and module.check_mode:
        current = check_mode_pool(module, current)

    exit_result(module, changed, current, "present")


def main():
    argument_spec = {
        "client_token": {"no_log": False, "type": "str"},
        "deletion_protection_enabled": {"default": False, "type": "bool"},
        "iso_country_code": {"type": "str"},
        "message_type": {"type": "str"},
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
    client = module.client(
        "pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff()
    )

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
