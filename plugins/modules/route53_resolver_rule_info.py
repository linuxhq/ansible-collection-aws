#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule_info
version_added: "1.9.0"
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def resource_tags(client, module, resource):
    if not resource.get("Arn"):
        return []
    try:
        return client.list_tags_for_resource(
            ResourceArn=resource["Arn"],
            aws_retry=True,
        ).get("Tags", [])
    except is_boto3_error_code("InvalidRequestException"):
        return []
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Route53 Resolver rule {resource['Arn']}",
        )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )
    resolver_rules = paginated_query_with_retries(client, "list_resolver_rules").get(
        "ResolverRules", []
    )
    if module.params["name"] is not None:
        resolver_rules = [
            rule for rule in resolver_rules if rule.get("Name") == module.params["name"]
        ]

    if module.params["name"] is None:
        associations = paginated_query_with_retries(
            client, "list_resolver_rule_associations"
        ).get("ResolverRuleAssociations", [])
    elif not resolver_rules:
        associations = []
    else:
        associations = paginated_query_with_retries(
            client,
            "list_resolver_rule_associations",
            Filters=ansible_dict_to_boto3_filter_list(
                {"ResolverRuleId": [rule["Id"] for rule in resolver_rules]}
            ),
        ).get("ResolverRuleAssociations", [])

    associations_by_rule_id = {}
    for association in associations:
        resolver_rule_id = association.get("ResolverRuleId")
        associations_by_rule_id.setdefault(resolver_rule_id, []).append(association)

    normalized_rules = []
    for rule in resolver_rules:
        normalized = boto3_resource_to_ansible_dict(
            dict(rule, Tags=resource_tags(client, module, rule)),
            transform_tags=True,
            force_tags=False,
        )
        resolver_rule_id = rule.get("Id")
        normalized["associations"] = boto3_resource_list_to_ansible_dict(
            associations_by_rule_id.get(resolver_rule_id, []),
            transform_tags=False,
            force_tags=False,
        )
        normalized["vpc_ids"] = []
        for association in normalized["associations"]:
            vpc_id = association.get("vpc_id")
            if vpc_id is not None:
                normalized["vpc_ids"].append(vpc_id)
        normalized_rules.append(normalized)

    module.exit_json(
        changed=False,
        resolver_rules=normalized_rules,
    )


if __name__ == "__main__":
    main()
