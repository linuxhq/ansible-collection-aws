#!/usr/bin/python
# -*- coding: utf-8 -*-
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
  id:
    description:
      - WAFv2 web ACL ID used to limit the result set.
      - The module lists web ACL summaries for the selected O(scope), filters
        by ID, and then gathers each full web ACL definition.
    type: str
  name:
    description:
      - WAFv2 web ACL name used to limit the result set.
      - The module lists web ACL summaries for the selected O(scope), filters
        by name, and then gathers each full web ACL definition.
    type: str
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
    name: molecule
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
            response = client.list_web_acls(**request, aws_retry=True)

            for summary in response.get("WebACLs", []):
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
        module.fail_json_aws(e, msg=f"Unable to list AWS WAFv2 web ACLs for {scope}")

    web_acls = []
    for summary in summaries:
        try:
            web_acls.append(
                client.get_web_acl(
                    Id=summary["Id"],
                    Name=summary["Name"],
                    Scope=scope,
                    aws_retry=True,
                ).get("WebACL", {})
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to get AWS WAFv2 web ACL "
                    f"{summary['Name']}/{summary['Id']}"
                ),
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
