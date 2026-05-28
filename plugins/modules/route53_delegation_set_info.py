#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set_info
short_description: Gather information about aws route53 delegation sets
description:
  - Gathers AWS Route53 reusable delegation sets.
author:
  - Taylor Kimball (@tkimball83)
options:
  ids:
    description:
      - Route53 reusable delegation set IDs used to limit the result set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather Route53 reusable delegation set information
  linuxhq.aws.route53_delegation_set_info:

- name: Gather a specific Route53 reusable delegation set
  linuxhq.aws.route53_delegation_set_info:
    ids:
      - N1PA6795SAMPLE
"""

RETURN = r"""
delegation_sets:
  description:
    - The reusable delegation sets for the current AWS account.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def route53_id(value):
    return value.rsplit("/", 1)[-1]


def list_reusable_delegation_sets(client, module):
    marker = None
    delegation_sets = []
    while True:
        request = {}
        if marker:
            request["Marker"] = marker
        try:
            response = client.list_reusable_delegation_sets(**request, aws_retry=True)
        except Exception as e:
            module.fail_json_aws(
                e, msg="Unable to list AWS Route53 reusable delegation sets"
            )
        delegation_sets.extend(response.get("DelegationSets", []))
        if not response.get("IsTruncated"):
            return delegation_sets
        marker = response.get("NextMarker")
        if not marker:
            module.fail_json(
                msg=(
                    "AWS Route53 reusable delegation sets response was "
                    "truncated without a NextMarker"
                )
            )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "ids": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())
    delegation_sets = []
    if module.params["ids"]:
        for delegation_set_id in module.params["ids"]:
            try:
                delegation_sets.append(
                    client.get_reusable_delegation_set(
                        Id=route53_id(delegation_set_id),
                        aws_retry=True,
                    ).get("DelegationSet", {})
                )
            except is_boto3_error_code("NoSuchDelegationSet"):
                continue
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to get AWS Route53 reusable delegation set "
                        f"{delegation_set_id}"
                    ),
                )
    else:
        delegation_sets = list_reusable_delegation_sets(client, module)

    module.exit_json(
        changed=False,
        delegation_sets=boto3_resource_list_to_ansible_dict(
            delegation_sets, transform_tags=False, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
