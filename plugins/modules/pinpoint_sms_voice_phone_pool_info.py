#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_pool_info
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
    default: SELF
    description:
      - The phone pool owner to query.
      - Mutually exclusive with O(pool_ids).
    type: str
  pool_ids:
    description:
      - Phone pool IDs used to limit the result set.
      - Mutually exclusive with O(owner).
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
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
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
)


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "max_results": {"type": "int"},
        "owner": {"choices": ["SELF", "SHARED"], "default": "SELF", "type": "str"},
        "pool_ids": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["owner", "pool_ids"]],
        supports_check_mode=True,
    )
    filters = module.params["filters"]
    max_results = module.params["max_results"]
    owner = module.params["owner"]
    pool_ids = module.params["pool_ids"]

    if max_results is not None and not 1 <= max_results <= 100:
        module.fail_json(msg="max_results must be between 1 and 100")

    client = module.client(
        "pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff()
    )

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
        {"describe_pools": tuple(request)},
    )

    try:
        pools = paginated_query_with_retries(
            client,
            "describe_pools",
            **request,
        ).get("Pools", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe Pinpoint SMS Voice V2 pools")

    normalized_pools = []
    for pool in pools:
        pool_id = pool.get("PoolId")
        origination_identities = []

        if pool_id:
            try:
                origination_identities = paginated_query_with_retries(
                    client,
                    "list_pool_origination_identities",
                    PoolId=pool_id,
                ).get("OriginationIdentities", [])
            except is_boto3_error_code("ResourceNotFoundException"):
                continue
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to list origination identities for Pinpoint SMS Voice "
                        f"V2 pool {pool_id}"
                    ),
                )

        arn = pool.get("PoolArn")
        tags = []

        if arn:
            try:
                tags = client.list_tags_for_resource(
                    ResourceArn=arn,
                    aws_retry=True,
                ).get("Tags", [])
            except is_boto3_error_code("ResourceNotFoundException"):
                continue
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to list tags for Pinpoint SMS Voice V2 pool {arn}",
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
