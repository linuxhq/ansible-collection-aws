#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set_info
version_added: "1.9.5"
short_description: Gather AWS Route53 reusable delegation set information
description:
  - Gathers AWS Route53 reusable delegation sets.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The reusable delegation set caller reference to query.
      - When omitted, all reusable delegation sets are returned.
    type: str
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
    name: molecule-01
"""

RETURN = r"""
delegation_sets:
  description:
    - The reusable delegation sets for the current AWS account.
  returned: always
  type: list
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())
    delegation_sets = []
    marker = None
    while True:
        request = {}
        if marker:
            request["Marker"] = marker
        response = client.list_reusable_delegation_sets(**request, aws_retry=True)
        delegation_sets.extend(response.get("DelegationSets", []))
        marker = response.get("NextMarker")
        if not response.get("IsTruncated") or not marker:
            break
    if module.params["name"] is not None:
        delegation_sets = [
            delegation_set
            for delegation_set in delegation_sets
            if delegation_set.get("CallerReference") == module.params["name"]
        ]

    module.exit_json(
        changed=False,
        delegation_sets=boto3_resource_list_to_ansible_dict(
            delegation_sets, transform_tags=False, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
