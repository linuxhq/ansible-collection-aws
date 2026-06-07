#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule_info
short_description: Gather information about aws route53 resolver rules
description:
  - Gathers information about AWS Route53 Resolver rules.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when listing Route53 Resolver rules.
      - Filter names and values are passed to the Route53 Resolver C(ListResolverRules) API.
    type: dict
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
    filters:
      Name: molecule-cloudflare
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


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )
    request = {}
    if module.params["filters"]:
        request["Filters"] = ansible_dict_to_boto3_filter_list(module.params["filters"])

    try:
        resolver_rules = paginated_query_with_retries(
            client, "list_resolver_rules", **request
        ).get("ResolverRules", [])

        if not module.params["filters"]:
            associations = paginated_query_with_retries(
                client, "list_resolver_rule_associations"
            ).get("ResolverRuleAssociations", [])
        elif not resolver_rules:
            associations = []
        else:
            resolver_rule_ids = []
            for rule in resolver_rules:
                resolver_rule_ids.append(rule["Id"])

            associations = paginated_query_with_retries(
                client,
                "list_resolver_rule_associations",
                Filters=ansible_dict_to_boto3_filter_list(
                    {"ResolverRuleId": resolver_rule_ids}
                ),
            ).get("ResolverRuleAssociations", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Route53 Resolver rules")

    associations_by_rule_id = {}
    for association in associations:
        resolver_rule_id = association.get("ResolverRuleId")
        associations_by_rule_id.setdefault(resolver_rule_id, []).append(association)

    normalized_rules = []
    for rule in resolver_rules:
        resolver_rule_id = rule.get("Id")
        tags = []
        if rule.get("Arn"):
            try:
                tags = paginated_query_with_retries(
                    client,
                    "list_tags_for_resource",
                    ResourceArn=rule["Arn"],
                ).get("Tags", [])
            except is_boto3_error_code("InvalidRequestException"):
                tags = []
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to list tags for AWS Route53 Resolver rule {rule['Arn']}",
                )

        normalized_rule = boto3_resource_to_ansible_dict(
            dict(rule, Tags=tags),
            transform_tags=True,
            force_tags=False,
        )

        normalized_rule["associations"] = boto3_resource_list_to_ansible_dict(
            associations_by_rule_id.get(resolver_rule_id, []),
            transform_tags=False,
            force_tags=False,
        )

        normalized_rule["vpc_ids"] = []

        for association in normalized_rule["associations"]:
            if association.get("vpc_id") is not None:
                normalized_rule["vpc_ids"].append(association["vpc_id"])
        normalized_rules.append(normalized_rule)

    module.exit_json(
        changed=False,
        resolver_rules=normalized_rules,
    )


if __name__ == "__main__":
    main()
