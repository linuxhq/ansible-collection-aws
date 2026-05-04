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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_resolver_rules(client, module):
    rules = []
    next_token = None

    while True:
        kwargs = {}
        if next_token:
            kwargs["NextToken"] = next_token

        try:
            response = client.list_resolver_rules(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Route53 Resolver rules",
            )

        rules.extend(response.get("ResolverRules", []))
        next_token = response.get("NextToken")
        if not next_token:
            break

    return rules


def list_resolver_rule_associations(client, module):
    associations = []
    next_token = None

    while True:
        kwargs = {}
        if next_token:
            kwargs["NextToken"] = next_token

        try:
            response = client.list_resolver_rule_associations(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Route53 Resolver rule associations",
            )

        associations.extend(response.get("ResolverRuleAssociations", []))
        next_token = response.get("NextToken")
        if not next_token:
            break

    return associations


def normalize(rule, associations):
    normalized = camel_dict_to_snake_dict(rule)
    if "target_ips" in normalized:
        normalized["target_ips"] = rule.get("TargetIps", [])
    normalized["associations"] = [
        camel_dict_to_snake_dict(association)
        for association in associations
        if association.get("ResolverRuleId") == rule.get("Id")
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
    resolver_rules = list_resolver_rules(client, module)
    resolver_rule_associations = list_resolver_rule_associations(client, module)

    if module.params["name"] is not None:
        resolver_rules = [
            rule for rule in resolver_rules if rule.get("Name") == module.params["name"]
        ]

    module.exit_json(
        changed=False,
        resolver_rules=[
            normalize(rule, resolver_rule_associations) for rule in resolver_rules
        ],
    )


if __name__ == "__main__":
    main()
