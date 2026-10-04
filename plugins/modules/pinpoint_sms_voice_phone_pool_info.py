#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_pool_info
version_added: '1.9.0'
short_description: Gather information about aws end user messaging sms phone pools
description:
  - Gathers information about AWS End User Messaging SMS phone pools.
  - This module maps to the Pinpoint SMS Voice V2 C(DescribePools) API,
    the API behind C(aws pinpoint-sms-voice-v2 describe-pools).
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing phone pools.
      - Filter names and values are passed to the Pinpoint SMS Voice V2
        C(DescribePools) API.
      - This must contain at most 20 filters.
    type: dict
  max_results:
    description:
      - The maximum number of results returned by each API call.
      - This must be between 1 and 100.
      - The module follows pagination and returns all matching phone pools.
    type: int
  owner:
    choices:
      - SELF
      - SHARED
    description:
      - The phone pool owner to query.
      - Defaults to C(SELF) when O(pool_ids) is omitted.
      - Mutually exclusive with O(pool_ids).
    type: str
  pool_ids:
    description:
      - Phone pool IDs used to limit the result set.
      - IDs that do not exist are omitted from the results.
      - This must contain at most 5 entries.
      - Mutually exclusive with O(owner).
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  diff_mode:
    description: Diff mode is not supported.
    support: none
  check_mode:
    description: This module does not modify AWS resources.
    support: full
"""

EXAMPLES = r"""
- name: Gather information about End User Messaging SMS phone pools
  linuxhq.aws.pinpoint_sms_voice_phone_pool_info:

- name: Gather information about selected phone pools
  linuxhq.aws.pinpoint_sms_voice_phone_pool_info:
    pool_ids:
      - pool-0123456789abcdef0123456789abcdef

- name: Gather information about transactional SMS phone pools
  linuxhq.aws.pinpoint_sms_voice_phone_pool_info:
    filters:
      message-type: TRANSACTIONAL
"""

RETURN = r"""
pool_ids:
  description:
    - A list of matching phone pool IDs.
  returned: always
  type: list
  elements: str
pools:
  description:
    - A list of End User Messaging SMS phone pools.
    - Each pool includes C(origination_identities) and C(tags) gathered by
      the module.
  returned: always
  type: list
  elements: dict
  contains:
    created_timestamp:
      description: The time the pool was created.
      returned: when returned by AWS
      type: str
    deletion_protection_enabled:
      description: Whether deletion protection is enabled.
      returned: when returned by AWS
      type: bool
    message_type:
      description: The type of messages sent from the pool.
      returned: when returned by AWS
      type: str
    opt_out_list_name:
      description: The OptOutList associated with the pool.
      returned: when returned by AWS
      type: str
    origination_identities:
      description: The origination identities associated with the pool.
      returned: when gathered by the module
      type: list
      elements: dict
      contains:
        iso_country_code:
          description: The two-character ISO country code.
          returned: when returned by AWS
          type: str
        origination_identity:
          description: The origination identity, such as a phone number ID or sender ID.
          returned: always
          type: str
        origination_identity_arn:
          description: The origination identity ARN.
          returned: when returned by AWS
          type: str
        number_capabilities:
          description: The origination identity capabilities.
          returned: when returned by AWS
          type: list
          elements: str
        phone_number:
          description: The phone number in E.164 format.
          returned: when the origination identity is a phone number
          type: str
    pool_arn:
      description: The pool ARN.
      returned: when returned by AWS
      type: str
    pool_id:
      description: The pool ID.
      returned: always
      type: str
    self_managed_opt_outs_enabled:
      description: Whether self-managed opt-outs are enabled.
      returned: when returned by AWS
      type: bool
    shared_routes_enabled:
      description: Whether shared routes are enabled.
      returned: when returned by AWS
      type: bool
    status:
      description: The pool status.
      returned: always
      type: str
      sample: ACTIVE
    tags:
      description: The pool tags with key case preserved.
      returned: when gathered by the module
      type: dict
    two_way_enabled:
      description: Whether two-way messaging is enabled.
      returned: when returned by AWS
      type: bool
"""

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
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def describe_pools_by_id(module, client, request):
    pools = []
    for pool_id in request["PoolIds"]:
        try:
            response = paginated_query_with_retries(
                client,
                "describe_pools",
                **dict(request, PoolIds=[pool_id]),
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to describe Pinpoint SMS Voice V2 pool {pool_id}")

        pools.extend(response.get("Pools", []))

    return pools


def validate_pool(module, pool):
    if (
        not isinstance(pool, dict)
        or not isinstance(pool.get("PoolId"), str)
        or ("PoolArn" in pool and not isinstance(pool["PoolArn"], str))
    ):
        module.fail_json(msg="AWS returned malformed Pinpoint SMS Voice V2 pool data")


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "max_results": {"type": "int"},
        "owner": {"choices": ["SELF", "SHARED"], "type": "str"},
        "pool_ids": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["owner", "pool_ids"]],
        supports_check_mode=True,
    )
    filters = module.params["filters"]
    max_results = module.params["max_results"]
    owner = module.params["owner"] or "SELF"
    pool_ids = list(dict.fromkeys(module.params["pool_ids"] or []))

    if max_results is not None and not 1 <= max_results <= 100:
        module.fail_json(msg="max_results must be between 1 and 100")

    if len(filters or {}) > 20:
        module.fail_json(msg="filters must contain at most 20 entries")

    if len(pool_ids) > 5:
        module.fail_json(msg="pool_ids must contain at most 5 entries")

    client = module.client("pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff())

    request = {}
    if max_results is not None:
        request["MaxResults"] = max_results

    if pool_ids:
        request["PoolIds"] = pool_ids
    else:
        request["Owner"] = owner

    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    require_client_methods(
        module,
        client,
        "Pinpoint SMS Voice V2",
        {
            "describe_pools": tuple(dict.fromkeys((*request, "MaxResults", "NextToken"))),
        },
    )

    if pool_ids:
        pools = describe_pools_by_id(module, client, request)
    else:
        pools = query_list(
            module,
            client,
            "describe_pools",
            "Pools",
            "Unable to describe Pinpoint SMS Voice V2 pools",
            **request,
        )

    if pools:
        require_client_methods(
            module,
            client,
            "Pinpoint SMS Voice V2",
            {
                "list_pool_origination_identities": (
                    "PoolId",
                    "MaxResults",
                    "NextToken",
                ),
                "list_tags_for_resource": ("ResourceArn",),
            },
        )

    normalized_pools = []
    for pool in pools:
        validate_pool(module, pool)
        pool_id = pool.get("PoolId")
        origination_identities = []

        if pool_id:
            try:
                response = paginated_query_with_retries(
                    client,
                    "list_pool_origination_identities",
                    PoolId=pool_id,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                continue
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to list origination identities for Pinpoint SMS Voice V2 pool {pool_id}",
                )

            origination_identities = response.get("OriginationIdentities") if isinstance(response, dict) else None
            if not isinstance(origination_identities, list) or any(
                not isinstance(identity, dict) or not isinstance(identity.get("OriginationIdentity"), str)
                for identity in origination_identities
            ):
                module.fail_json(
                    msg=f"AWS returned malformed origination identities for Pinpoint SMS Voice V2 pool {pool_id}"
                )

        arn = pool.get("PoolArn")
        tags = []

        if arn:
            try:
                response = client.list_tags_for_resource(
                    ResourceArn=arn,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                continue
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to list tags for Pinpoint SMS Voice V2 pool {arn}",
                )

            tags = require_valid_tag_list(
                module,
                response.get("Tags", []) if isinstance(response, dict) else None,
                f"AWS returned malformed tags for Pinpoint SMS Voice V2 pool {arn}",
            )

        normalized_pools.append(
            boto3_resource_to_ansible_dict(
                dict(pool, OriginationIdentities=origination_identities, Tags=tags),
                transform_tags=True,
                force_tags=False,
            )
        )

    matching_pool_ids = []
    for pool in normalized_pools:
        pool_id = pool.get("pool_id")

        if pool_id:
            matching_pool_ids.append(pool_id)

    module.exit_json(
        changed=False,
        pool_ids=matching_pool_ids,
        pools=normalized_pools,
    )


if __name__ == "__main__":
    main()
