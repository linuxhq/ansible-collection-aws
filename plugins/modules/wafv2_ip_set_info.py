#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_ip_set_info
version_added: 1.9.1
short_description: Gather information about AWS WAFv2 IP sets
description:
  - Gathers information about AWS WAFv2 IP sets.
  - Lists IP sets for the requested scope and returns each full IP set definition.
author:
  - Taylor Kimball (@tkimball83)
options:
  scope:
    description:
      - The scope of the IP sets to gather.
      - Use C(cloudfront) for global IP sets and C(regional) for regional IP sets.
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.wafv2 import (
    list_wafv2_summaries,
    normalize_wafv2_resource,
)


def get_ip_set(client, module, scope, summary):
    get_ip_set = AWSRetry.jittered_backoff()(client.get_ip_set)
    try:
        response = get_ip_set(
            Id=summary["Id"],
            Name=summary["Name"],
            Scope=scope,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS WAFv2 IP set {summary['Name']}",
        )

    return response.get("IPSet", {})


def main():
    argument_spec = {
        "scope": {
            "choices": ["cloudfront", "regional"],
            "default": "regional",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("wafv2")

    scope = module.params["scope"].upper()
    summaries = list_wafv2_summaries(
        client,
        module,
        scope,
        "list_ip_sets",
        "IPSets",
        "Unable to list AWS WAFv2 IP sets",
    )
    ip_sets = [
        normalize_wafv2_resource(get_ip_set(client, module, scope, summary))
        for summary in summaries
        if summary.get("Id") and summary.get("Name")
    ]

    module.exit_json(
        changed=False,
        ip_sets=ip_sets,
        scope=scope.lower(),
    )


if __name__ == "__main__":
    main()
