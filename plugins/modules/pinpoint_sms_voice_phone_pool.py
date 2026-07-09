#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - When set with O(state=present) and the pool does not exist, a new
        pool with a new ID is created.
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
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def apply_tag_deltas(pool, tags_to_set, tag_keys_to_unset):
    updated = dict(pool)
    updated_tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        updated_tags.pop(tag_key, None)
    updated_tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(updated_tags)
    return updated


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


def pool_with_origination_identities(client, module, pool):
    pool = dict(pool)
    pool_id = pool.get("PoolId")

    if pool_id:
        try:
            pool["OriginationIdentities"] = paginated_query_with_retries(
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

    else:
        pool["OriginationIdentities"] = []

    return pool


def pool_with_tags(client, module, pool):
    pool = dict(pool)
    arn = pool.get("PoolArn")
    tags = {}

    if arn:
        try:
            tags = boto3_tag_list_to_ansible_dict(
                client.list_tags_for_resource(
                    ResourceArn=arn,
                    aws_retry=True,
                ).get("Tags", [])
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 pool {arn}"
            )

    pool["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return pool


def get_pool_by_id(client, module, pool_id):
    pools = describe_pools(client, module, PoolIds=[pool_id])

    if not pools:
        return None

    pool = pool_with_origination_identities(client, module, pools[0])

    return pool_with_tags(client, module, pool)


def wait_for_pool_active(client, module, pool_id):
    deadline = time.monotonic() + module.params["wait_timeout"]
    pool = {}

    while time.monotonic() < deadline:
        pools = describe_pools(client, module, PoolIds=[pool_id])
        pool = pools[0] if pools else {}
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
        time.sleep(module.params["wait_delay"])

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


def find_pool(client, module):
    if module.params["pool_id"] is not None:
        return get_pool_by_id(client, module, module.params["pool_id"])

    filters = ansible_dict_to_boto3_filter_list(
        {"message-type": module.params["message_type"]}
    )
    iso_country_code = module.params["iso_country_code"]

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

            if (
                iso_country_code is not None
                and origination.get("IsoCountryCode") != iso_country_code
            ):
                continue

            return pool_with_tags(client, module, pool)

    return None


def exit_result(module, changed, pool):
    normalized_pool = boto3_resource_to_ansible_dict(
        pool or {}, transform_tags=True, force_tags=False
    )
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
    current = pools[0] if pools else None

    if current is not None and current.get("Status") == "DELETING":
        current = None

    changed = current is not None
    response = current

    if changed and not module.check_mode:
        try:
            response = client.delete_pool(
                PoolId=pool_id,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            response = None
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to delete Pinpoint SMS Voice V2 pool {pool_id}"
            )

        if response is not None:
            response.pop("ResponseMetadata", None)

    exit_result(module, changed, response or current)


def ensure_present(client, module):
    deletion_protection_enabled = module.params["deletion_protection_enabled"]
    message_type = module.params["message_type"]
    wait = module.params["wait"]
    current = find_pool(client, module)

    if current is not None and current.get("MessageType") != message_type:
        module.fail_json(
            msg=(
                "Cannot modify message_type for existing Pinpoint SMS Voice V2 "
                f"pool {current.get('PoolId')}"
            )
        )

    if (
        wait
        and current is not None
        and current.get("Status") != "ACTIVE"
        and current.get("PoolId")
    ):
        wait_for_pool_active(client, module, current["PoolId"])
        current = get_pool_by_id(client, module, current["PoolId"]) or current

    update_request = {}
    if (
        current is not None
        and current.get("DeletionProtectionEnabled") != deletion_protection_enabled
    ):
        update_request["DeletionProtectionEnabled"] = deletion_protection_enabled

    user_tags = module.params["tags"]
    tags = dict(user_tags or {})
    tags["Name"] = module.params["name"]

    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
        tags,
        purge_tags=module.params["purge_tags"] if user_tags is not None else False,
    )

    changed = current is None or bool(
        update_request or tags_to_set or tag_keys_to_unset
    )

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
            except Exception as e:
                module.fail_json_aws(
                    e, msg="Unable to create Pinpoint SMS Voice V2 pool"
                )

            current.pop("ResponseMetadata", None)
        else:
            if update_request:
                try:
                    current = client.update_pool(
                        PoolId=current["PoolId"],
                        **update_request,
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to update Pinpoint SMS Voice V2 pool "
                            f"{current['PoolId']}"
                        ),
                    )

                current.pop("ResponseMetadata", None)

            arn = current.get("PoolArn")

            if (tags_to_set or tag_keys_to_unset) and not arn:
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
                        e,
                        msg=(
                            "Unable to remove tags from Pinpoint SMS Voice V2 "
                            f"pool {arn}"
                        ),
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

            if not update_request:
                current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

        if wait and current.get("Status") != "ACTIVE" and current.get("PoolId"):
            wait_for_pool_active(client, module, current["PoolId"])
            pool_changed = True

        if pool_changed and current.get("PoolId"):
            current = get_pool_by_id(client, module, current["PoolId"]) or current
    elif changed and module.check_mode:
        current = dict(current or {})
        current.update(
            {
                "DeletionProtectionEnabled": deletion_protection_enabled,
                "MessageType": message_type,
                "Status": current.get("Status") or "ACTIVE",
            }
        )
        current["OriginationIdentities"] = current.get("OriginationIdentities") or [
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

        if iso_country_code is not None and not re.fullmatch(
            r"[A-Z]{2}", iso_country_code
        ):
            module.fail_json(
                msg="iso_country_code must be exactly two uppercase letters"
            )

        if module.params["wait"]:
            if module.params["wait_delay"] < 1:
                module.fail_json(msg="wait_delay must be 1 or greater")

            if module.params["wait_timeout"] < 1:
                module.fail_json(msg="wait_timeout must be 1 or greater")

    client = module.client(
        "pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff()
    )
    method_names = {"describe_pools"}
    if state == "present":
        method_names.update(
            {
                "create_pool",
                "list_pool_origination_identities",
                "list_tags_for_resource",
                "tag_resource",
                "update_pool",
            }
        )
        if module.params["tags"] is not None and module.params["purge_tags"]:
            method_names.add("untag_resource")
    elif state == "absent":
        method_names.add("delete_pool")
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
        "create_pool": {
            "ClientToken",
            "DeletionProtectionEnabled",
            "IsoCountryCode",
            "MessageType",
            "OriginationIdentity",
            "Tags",
        },
        "delete_pool": {"PoolId"},
        "describe_pools": {"Filters", "Owner", "PoolIds"},
        "list_pool_origination_identities": {"PoolId"},
        "list_tags_for_resource": {"ResourceArn"},
        "tag_resource": {"ResourceArn", "Tags"},
        "untag_resource": {"ResourceArn", "TagKeys"},
        "update_pool": {"DeletionProtectionEnabled", "PoolId"},
    }
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
