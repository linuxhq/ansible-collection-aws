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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_ip_set_summaries(client, module, scope):
    summaries = []
    next_marker = None

    try:
        while True:
            request = {"Scope": scope}
            if next_marker:
                request["NextMarker"] = next_marker

            response = client.list_ip_sets(**request)
            summaries.extend(response.get("IPSets", []))
            next_marker = response.get("NextMarker")
            if not next_marker:
                break
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS WAFv2 IP sets")

    return summaries


def get_ip_set(client, module, scope, summary):
    try:
        response = client.get_ip_set(
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
    summaries = list_ip_set_summaries(client, module, scope)
    ip_sets = [
        camel_dict_to_snake_dict(get_ip_set(client, module, scope, summary))
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
