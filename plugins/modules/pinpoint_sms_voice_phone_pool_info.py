#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: pinpoint_sms_voice_phone_pool_info
version_added: "1.9.6"
short_description: Gather information about AWS End User Messaging SMS phone pools
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
      - The module follows pagination and returns all matching phone pools.
    type: int
  owner:
    choices:
      - SELF
      - SHARED
    default: SELF
    description:
      - The phone pool owner to query.
      - This is not sent when O(pool_ids) is set because C(DescribePools) does
        not allow both parameters together.
    type: str
  pool_ids:
    description:
      - Phone pool IDs used to limit the result set.
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
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def build_request(module):
    pool_ids = module.params["pool_ids"] or None
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "max_results": module.params["max_results"],
                "owner": module.params["owner"] if not pool_ids else None,
                "pool_ids": pool_ids,
            },
            capitalize_first=True,
        )
    )
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])
    return request


def pool_tags(client, module, pool):
    arn = pool.get("PoolArn")
    if not arn:
        return []
    try:
        return client.list_tags_for_resource(
            ResourceArn=arn,
            aws_retry=True,
        ).get("Tags", [])
    except is_boto3_error_code("ResourceNotFoundException"):
        return []
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to list tags for Pinpoint SMS Voice V2 pool {arn}"
        )


def pool_origination_identities(client, module, pool):
    pool_id = pool.get("PoolId")
    if not pool_id:
        return []
    try:
        return paginated_query_with_retries(
            client,
            "list_pool_origination_identities",
            PoolId=pool_id,
        ).get("OriginationIdentities", [])
    except is_boto3_error_code("ResourceNotFoundException"):
        return []
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list origination identities for Pinpoint SMS Voice "
                f"V2 pool {pool_id}"
            ),
        )


def normalize_pool(client, module, pool):
    return boto3_resource_to_ansible_dict(
        dict(
            pool,
            OriginationIdentities=pool_origination_identities(client, module, pool),
            Tags=pool_tags(client, module, pool),
        ),
        transform_tags=True,
        force_tags=False,
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
        supports_check_mode=True,
    )
    client = module.client(
        "pinpoint-sms-voice-v2", retry_decorator=AWSRetry.jittered_backoff()
    )

    try:
        pools = paginated_query_with_retries(
            client,
            "describe_pools",
            **build_request(module),
        ).get("Pools", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe Pinpoint SMS Voice V2 pools")

    pools = [normalize_pool(client, module, pool) for pool in pools]
    module.exit_json(
        changed=False,
        pool_ids=[pool["pool_id"] for pool in pools if pool.get("pool_id")],
        pools=pools,
    )


if __name__ == "__main__":
    main()
