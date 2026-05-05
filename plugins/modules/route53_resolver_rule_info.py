#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule_info
version_added: 1.9.1
short_description: Gather information about AWS Route53 Resolver rules
description:
  - Gathers information about AWS Route53 Resolver rules.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The Route53 Resolver rule name to query.
      - When omitted, all resolver rules are returned.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about Route53 Resolver rules
  linuxhq.aws.route53_resolver_rule_info:

- name: Gather information about a single Route53 Resolver rule
  linuxhq.aws.route53_resolver_rule_info:
    name: molecule-cloudflare
"""

RETURN = r"""
resolver_rules:
  description:
    - The Route53 Resolver rules.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
    filter_aws_resources,
)


def group_associations_by_rule_id(associations):
    associations_by_rule_id = {}
    for association in associations:
        associations_by_rule_id.setdefault(
            association.get("ResolverRuleId"), []
        ).append(association)
    return associations_by_rule_id


def normalize_resolver_rule_with_associations(rule, associations_by_rule_id):
    normalized = aws_resource_to_snake_dict(rule)
    normalized["associations"] = [
        aws_resource_to_snake_dict(association)
        for association in associations_by_rule_id.get(rule.get("Id"), [])
    ]
    normalized["vpc_ids"] = [
        association["vpc_id"]
        for association in normalized["associations"]
        if association.get("vpc_id") is not None
    ]
    return normalized


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53resolver")
    resolver_rules = aws_paginated_list(
        client,
        module,
        "list_resolver_rules",
        "ResolverRules",
    )
    associations_by_rule_id = group_associations_by_rule_id(
        aws_paginated_list(
            client,
            module,
            "list_resolver_rule_associations",
            "ResolverRuleAssociations",
        )
    )

    if module.params["name"] is not None:
        resolver_rules = filter_aws_resources(
            resolver_rules,
            name=module.params["name"],
        )

    module.exit_json(
        changed=False,
        resolver_rules=[
            normalize_resolver_rule_with_associations(rule, associations_by_rule_id)
            for rule in resolver_rules
        ],
    )


if __name__ == "__main__":
    main()
