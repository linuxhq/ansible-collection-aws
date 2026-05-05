#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set_info
version_added: 1.9.1
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
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_marker_paginated_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_matches,
    aws_resource_to_snake_dict,
)


def list_normalized_delegation_sets(client, module):
    return [
        aws_resource_to_snake_dict(delegation_set)
        for delegation_set in aws_marker_paginated_list(
            client,
            module,
            "list_reusable_delegation_sets",
            "DelegationSets",
            truncated_result="IsTruncated",
        )
        if not aws_resource_matches(delegation_set, caller_reference=None)
        and (
            module.params["name"] is None
            or aws_resource_matches(
                delegation_set,
                caller_reference=module.params["name"],
            )
        )
    ]


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53")

    module.exit_json(
        changed=False,
        delegation_sets=list_normalized_delegation_sets(client, module),
    )


if __name__ == "__main__":
    main()
