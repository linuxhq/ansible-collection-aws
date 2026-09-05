#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_ip_set_info
short_description: Gather information about AWS WAFv2 IP sets
description:
  - Gathers information about AWS WAFv2 IP sets.
  - Lists IP sets for the requested scope and returns each full IP set definition.
author:
  - Taylor Kimball (@tkimball83)
options:
  id:
    description:
      - WAFv2 IP set ID used to limit the result set.
      - This must not be empty when specified.
      - The module lists IP set summaries for the selected O(scope), filters by
        ID, and then gathers each full IP set definition.
    type: str
  name:
    description:
      - WAFv2 IP set name used to limit the result set.
      - This must not be empty when specified.
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
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
  contains:
    addresses:
      description: IP addresses and CIDR ranges included in the IP set.
      returned: always
      type: list
      elements: str
    arn:
      description: ARN of the IP set.
      returned: always
      type: str
    description:
      description: Description of the IP set.
      returned: when available
      type: str
    id:
      description: ID of the IP set.
      returned: always
      type: str
    ip_address_version:
      description: IP address version used by the IP set.
      returned: always
      type: str
    name:
      description: Name of the IP set.
      returned: always
      type: str
scope:
  description: The AWS WAFv2 scope that was queried.
  returned: always
  type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
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
    target_id = module.params["id"]
    target_name = module.params["name"]
    if target_id == "":
        module.fail_json(msg="id must not be empty")
    if target_name == "":
        module.fail_json(msg="name must not be empty")

    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(
        module,
        client,
        "WAFv2",
        {
            "list_ip_sets": ("Limit", "NextMarker", "Scope"),
            "get_ip_set": ("Id", "Name", "Scope"),
        },
    )

    scope = module.params["scope"].upper()
    response_summaries = query_list(
        module,
        client,
        "list_ip_sets",
        "IPSets",
        f"Unable to list AWS WAFv2 IP sets for {scope}",
        Scope=scope,
        Limit=100,
    )
    if not isinstance(response_summaries, list):
        module.fail_json(msg=f"Unexpected response while listing AWS WAFv2 IP sets for {scope}")

    summaries = []
    for summary in response_summaries:
        summary_id = summary.get("Id") if isinstance(summary, dict) else None
        summary_name = summary.get("Name") if isinstance(summary, dict) else None
        if target_id and summary_id != target_id:
            continue
        if target_name and summary_name != target_name:
            continue
        if not isinstance(summary_id, str) or not summary_id:
            module.fail_json(msg=f"Unexpected response while listing AWS WAFv2 IP sets for {scope}; invalid ID")
        if not isinstance(summary_name, str) or not summary_name:
            module.fail_json(msg=f"Unexpected response while listing AWS WAFv2 IP sets for {scope}; invalid name")
        summaries.append(summary)
        if target_id or target_name:
            break

    ip_sets = []
    for summary in summaries:
        try:
            response = client.get_ip_set(
                Id=summary["Id"],
                Name=summary["Name"],
                Scope=scope,
                aws_retry=True,
            )
        except is_boto3_error_code("WAFNonexistentItemException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to get AWS WAFv2 IP set " f"{summary['Name']}/{summary['Id']}"),
            )
        ip_set = response.get("IPSet") if isinstance(response, dict) else None
        if not isinstance(ip_set, dict):
            module.fail_json(
                msg=f"Unexpected response while getting AWS WAFv2 IP set {summary['Name']}/{summary['Id']}"
            )
        ip_sets.append(ip_set)

    module.exit_json(
        changed=False,
        ip_sets=boto3_resource_list_to_ansible_dict(ip_sets, transform_tags=False, force_tags=False),
        scope=scope.lower(),
    )


if __name__ == "__main__":
    main()
