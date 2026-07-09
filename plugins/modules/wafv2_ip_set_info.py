#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_ip_set_info
short_description: Gather information about aws wafv2 ip sets
description:
  - Gathers information about AWS WAFv2 IP sets.
  - Lists IP sets for the requested scope and returns each full IP set definition.
author:
  - Taylor Kimball (@tkimball83)
options:
  id:
    description:
      - WAFv2 IP set ID used to limit the result set.
      - The module lists IP set summaries for the selected O(scope), filters by
        ID, and then gathers each full IP set definition.
    type: str
  name:
    description:
      - WAFv2 IP set name used to limit the result set.
      - The module lists IP set summaries for the selected O(scope), filters by
        name, and then gathers each full IP set definition.
      - An IP set that does not exist results in an empty list.
    type: str
  scope:
    description:
      - The scope of the IP sets to gather.
      - Use C(cloudfront) for global IP sets and C(regional) for regional IP sets.
      - V(cloudfront) requires the C(us-east-1) region.
    choices:
      - cloudfront
      - regional
    default: regional
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about regional WAFv2 IP sets
  linuxhq.aws.wafv2_ip_set_info:

- name: Gather information about CloudFront WAFv2 IP sets
  linuxhq.aws.wafv2_ip_set_info:
    scope: cloudfront
    region: us-east-1

- name: Gather information about selected WAFv2 IP sets
  linuxhq.aws.wafv2_ip_set_info:
    name: molecule
"""

RETURN = r"""
ip_sets:
  description:
    - A list of AWS WAFv2 IP set definitions.
  returned: always
  type: list
  elements: dict
scope:
  description: The AWS WAFv2 scope that was queried.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def main():
    argument_spec = {
        "id": {"type": "str"},
        "name": {"type": "str"},
        "scope": {
            "choices": ["cloudfront", "regional"],
            "default": "regional",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())

    scope = module.params["scope"].upper()
    target_id = module.params["id"]
    target_name = module.params["name"]
    single_target = bool(target_id or target_name)
    summaries = []
    marker = None

    try:
        while True:
            request = {"Scope": scope, "Limit": 100}
            if marker:
                request["NextMarker"] = marker
            response = client.list_ip_sets(**request, aws_retry=True)

            for summary in response.get("IPSets", []):
                if target_id and summary.get("Id") != target_id:
                    continue
                if target_name and summary.get("Name") != target_name:
                    continue
                summaries.append(summary)
                if single_target:
                    break

            if single_target and summaries:
                break
            marker = response.get("NextMarker")

            if not marker:
                break
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to list AWS WAFv2 IP sets for {scope}")

    ip_sets = []
    for summary in summaries:
        try:
            ip_sets.append(
                client.get_ip_set(
                    Id=summary["Id"],
                    Name=summary["Name"],
                    Scope=scope,
                    aws_retry=True,
                ).get("IPSet", {})
            )
        except is_boto3_error_code("WAFNonexistentItemException"):
            continue
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to get AWS WAFv2 IP set "
                    f"{summary['Name']}/{summary['Id']}"
                ),
            )

    module.exit_json(
        changed=False,
        ip_sets=boto3_resource_list_to_ansible_dict(
            ip_sets, transform_tags=False, force_tags=False
        ),
        scope=scope.lower(),
    )


if __name__ == "__main__":
    main()
