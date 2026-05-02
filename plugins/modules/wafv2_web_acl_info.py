#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_info
version_added: 1.9.1
short_description: Gather information about AWS WAFv2 web ACLs
description:
  - Gathers information about AWS WAFv2 web ACLs.
  - Lists web ACLs for the requested scope and returns each full web ACL definition.
author:
  - Taylor Kimball (@tkimball83)
options:
  scope:
    description:
      - The scope of the web ACLs to gather.
      - Use C(cloudfront) for global web ACLs and C(regional) for regional web ACLs.
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
- name: Gather information about regional WAFv2 web ACLs
  linuxhq.aws.wafv2_web_acl_info:

- name: Gather information about CloudFront WAFv2 web ACLs
  linuxhq.aws.wafv2_web_acl_info:
    scope: cloudfront
    region: us-east-1
"""

RETURN = r"""
scope:
  description: The AWS WAFv2 scope that was queried.
  returned: always
  type: str
web_acls:
  description:
    - A list of AWS WAFv2 web ACL definitions.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_web_acl_summaries(client, module, scope):
    summaries = []
    next_marker = None

    try:
        while True:
            request = {"Scope": scope}
            if next_marker:
                request["NextMarker"] = next_marker

            response = client.list_web_acls(**request)
            summaries.extend(response.get("WebACLs", []))
            next_marker = response.get("NextMarker")
            if not next_marker:
                break
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS WAFv2 web ACLs")

    return summaries


def get_web_acl(client, module, scope, summary):
    try:
        response = client.get_web_acl(
            Id=summary["Id"],
            Name=summary["Name"],
            Scope=scope,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS WAFv2 web ACL {summary['Name']}",
        )

    return response.get("WebACL", {})


def main() -> None:
    argument_spec = {
        "scope": {
            "choices": ["cloudfront", "regional"],
            "default": "regional",
            "type": "str",
        },
        "validate_certs": {"default": True, "type": "bool"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("wafv2")

    scope = module.params["scope"].upper()
    summaries = list_web_acl_summaries(client, module, scope)

    web_acls = [
        camel_dict_to_snake_dict(get_web_acl(client, module, scope, summary))
        for summary in summaries
        if summary.get("Id") and summary.get("Name")
    ]

    module.exit_json(
        changed=False,
        scope=scope.lower(),
        web_acls=web_acls,
    )


if __name__ == "__main__":
    main()
