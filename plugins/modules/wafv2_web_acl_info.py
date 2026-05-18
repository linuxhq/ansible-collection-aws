#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_info
short_description: Gather information about aws wafv2 web acls
description:
  - Gathers information about AWS WAFv2 web ACLs.
  - Lists web ACLs for the requested scope and returns each full web ACL definition.
author:
  - Taylor Kimball (@tkimball83)
options:
  ids:
    description:
      - WAFv2 web ACL IDs used to limit the result set.
      - The module lists web ACL summaries for the selected O(scope), filters
        by ID, and then gathers each full web ACL definition.
    elements: str
    type: list
  names:
    description:
      - WAFv2 web ACL names used to limit the result set.
      - The module lists web ACL summaries for the selected O(scope), filters
        by name, and then gathers each full web ACL definition.
    elements: str
    type: list
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

- name: Gather information about selected WAFv2 web ACLs
  linuxhq.aws.wafv2_web_acl_info:
    names:
      - molecule
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def summary_matches(module, summary):
    if module.params["ids"] and summary.get("Id") not in module.params["ids"]:
        return False
    if module.params["names"] and summary.get("Name") not in module.params["names"]:
        return False
    return True


def requested_summaries_found(module, remaining_ids, remaining_names):
    if module.params["ids"]:
        return not remaining_ids
    if module.params["names"]:
        return not remaining_names
    return False


def list_web_acl_summaries(client, module, scope):
    can_paginate = getattr(client, "can_paginate", lambda operation_name: False)
    if can_paginate("list_web_acls") and not (
        module.params["ids"] or module.params["names"]
    ):
        return paginated_query_with_retries(
            client,
            "list_web_acls",
            Scope=scope,
        ).get("WebACLs", [])

    marker = None
    web_acls = []
    remaining_ids = set(module.params["ids"] or [])
    remaining_names = set(module.params["names"] or [])
    while True:
        request = {"Scope": scope, "Limit": 100}
        if marker:
            request["NextMarker"] = marker
        response = client.list_web_acls(**request, aws_retry=True)
        for summary in response.get("WebACLs", []):
            web_acls.append(summary)
            remaining_ids.discard(summary.get("Id"))
            remaining_names.discard(summary.get("Name"))
            if requested_summaries_found(module, remaining_ids, remaining_names):
                return web_acls
        marker = response.get("NextMarker")
        if not marker:
            break
    return web_acls


def main():
    argument_spec = {
        "ids": {"elements": "str", "type": "list"},
        "names": {"elements": "str", "type": "list"},
        "scope": {
            "choices": ["cloudfront", "regional"],
            "default": "regional",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())

    scope = module.params["scope"].upper()
    web_acls = []
    for summary in list_web_acl_summaries(client, module, scope):
        if not summary_matches(module, summary):
            continue
        web_acls.append(
            client.get_web_acl(
                Id=summary["Id"],
                Name=summary["Name"],
                Scope=scope,
                aws_retry=True,
            ).get("WebACL", {})
        )

    module.exit_json(
        changed=False,
        scope=scope.lower(),
        web_acls=boto3_resource_list_to_ansible_dict(
            web_acls, transform_tags=False, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
