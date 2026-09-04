#!/usr/bin/python
# Copyright: Ansible Project
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
attributes:
  check_mode:
    description: This module does not modify AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - Each rule includes C(associations), C(tags), and C(vpc_ids) gathered
      by the module.
  returned: always
  type: list
  elements: dict
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53resolver", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "Route53 Resolver",
        {
            "list_resolver_rules": ("Filters", "MaxResults", "NextToken"),
            "list_resolver_rule_associations": (
                "Filters",
                "MaxResults",
                "NextToken",
            ),
            "list_tags_for_resource": ("MaxResults", "NextToken", "ResourceArn"),
        },
    )

    filters = module.params["filters"]
    request = {}
    if filters:
        request["Filters"] = ansible_dict_to_boto3_filter_list(filters)

    resolver_rules = query_list(
        module,
        client,
        "list_resolver_rules",
        "ResolverRules",
        "Unable to list AWS Route53 Resolver rules",
        **request,
    )
    resolver_rules = [validate_resolver_rule(module, rule) for rule in resolver_rules]

    if not resolver_rules:
        associations = []
    else:
        association_request = {}
        if filters:
            association_request["Filters"] = ansible_dict_to_boto3_filter_list(
                {"ResolverRuleId": [rule["Id"] for rule in resolver_rules]}
            )

        associations = query_list(
            module,
            client,
            "list_resolver_rule_associations",
            "ResolverRuleAssociations",
            "Unable to list AWS Route53 Resolver rule associations",
            **association_request,
        )

    associations_by_rule_id = {}
    for association in associations:
        association = validate_association(module, association)
        resolver_rule_id = association["ResolverRuleId"]
        associations_by_rule_id.setdefault(resolver_rule_id, []).append(association)

    normalized_rules = []
    for rule in resolver_rules:
        resolver_rule_id = rule.get("Id")
        tags = []
        if rule.get("Arn"):
            try:
                response = paginated_query_with_retries(
                    client,
                    "list_tags_for_resource",
                    ResourceArn=rule["Arn"],
                )
            except is_boto3_error_code("InvalidRequestException"):
                tags = []
            except is_boto3_error_code("ResourceNotFoundException"):
                continue
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to list tags for AWS Route53 Resolver rule {rule['Arn']}",
                )
            else:
                tags = validate_tags(module, response_items(module, response, "Tags", "list_tags_for_resource"))

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

        normalized_rule["vpc_ids"] = [
            association["vpc_id"]
            for association in normalized_rule["associations"]
            if association.get("vpc_id") is not None
        ]
        normalized_rules.append(normalized_rule)

    module.exit_json(
        changed=False,
        resolver_rules=normalized_rules,
    )


def response_items(module, response, key, operation):
    if not isinstance(response, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid response")
    items = response.get(key, [])
    if not isinstance(items, list):
        module.fail_json(msg=f"{operation}: AWS returned an invalid {key} value")
    return items


def validate_resolver_rule(module, rule):
    if not isinstance(rule, dict):
        module.fail_json(msg="list_resolver_rules: AWS returned an invalid resolver rule")
    rule_id = rule.get("Id")
    if not isinstance(rule_id, str) or not rule_id:
        module.fail_json(msg="list_resolver_rules: AWS returned a resolver rule without a valid ID")
    if "Arn" in rule and not isinstance(rule["Arn"], str):
        module.fail_json(msg="list_resolver_rules: AWS returned an invalid resolver rule ARN")
    return rule


def validate_association(module, association):
    if not isinstance(association, dict):
        module.fail_json(msg="list_resolver_rule_associations: AWS returned an invalid association")
    resolver_rule_id = association.get("ResolverRuleId")
    if not isinstance(resolver_rule_id, str) or not resolver_rule_id:
        module.fail_json(msg="list_resolver_rule_associations: AWS returned an association without a rule ID")
    if "VPCId" in association and not isinstance(association["VPCId"], str):
        module.fail_json(msg="list_resolver_rule_associations: AWS returned an invalid association VPC ID")
    return association


def validate_tags(module, tags):
    for tag in tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str):
            module.fail_json(msg="list_tags_for_resource: AWS returned an invalid tag")
    return tags


if __name__ == "__main__":
    main()
