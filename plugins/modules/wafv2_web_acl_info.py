#!/usr/bin/python
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_marker_paginated_list,
    aws_resource,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
)


def get_web_acl(client, module, scope, summary):
    return aws_resource(
        client,
        module,
        "get_web_acl",
        "WebACL",
        default={},
        Id=summary["Id"],
        Name=summary["Name"],
        Scope=scope,
    )


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
    summaries = aws_marker_paginated_list(
        client,
        module,
        "list_web_acls",
        "WebACLs",
        marker_arg="NextMarker",
        initial_kwargs={"Scope": scope},
    )

    web_acls = [
        aws_resource_to_snake_dict(get_web_acl(client, module, scope, summary))
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
