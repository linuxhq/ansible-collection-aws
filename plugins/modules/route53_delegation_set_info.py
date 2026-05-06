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
from ansible_collections.linuxhq.aws.plugins.module_utils.route53 import (
    get_reusable_delegation_set_by_name,
    list_reusable_delegation_sets,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53")
    if module.params["name"] is None:
        delegation_sets = list_reusable_delegation_sets(client, module)
    else:
        delegation_set = get_reusable_delegation_set_by_name(
            client,
            module,
            module.params["name"],
        )
        delegation_sets = [delegation_set] if delegation_set is not None else []

    module.exit_json(
        changed=False,
        delegation_sets=aws_resource_list_to_snake_dicts(delegation_sets),
    )


if __name__ == "__main__":
    main()
