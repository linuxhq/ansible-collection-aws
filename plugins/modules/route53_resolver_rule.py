#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule
short_description: Manage aws route53 resolver rules
description:
  - Manages AWS Route53 Resolver rules.
  - Updates resolver endpoint and target IP settings for existing rules.
author:
  - Taylor Kimball (@tkimball83)
options:
  domain_name:
    description:
      - The domain name for the resolver rule.
      - This is required when O(state=present).
    type: str
  name:
    description:
      - The resolver rule name.
    required: true
    type: str
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  resolver_endpoint_id:
    description:
      - The resolver endpoint ID for the rule.
      - This is required when O(state=present).
    type: str
  rule_type:
    description:
      - The resolver rule type.
      - Only V(forward) rules can be managed by this module; C(SYSTEM) and
        C(RECURSIVE) rules do not accept target IPs or resolver endpoints.
      - This is required when O(state=present).
    type: str
  state:
    description:
      - Whether the resolver rule should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the resolver rule.
    type: dict
  target_ips:
    description:
      - The target IP definitions for forwarding rules.
      - This is required when O(state=present).
    elements: dict
    suboptions:
      ip:
        description:
          - The IPv4 address of the target.
          - Mutually exclusive with O(target_ips[].ipv6).
        type: str
      ipv6:
        description:
          - The IPv6 address of the target.
          - Mutually exclusive with O(target_ips[].ip).
        type: str
      port:
        description:
          - The port for the target.
        type: int
      protocol:
        description:
          - The protocol for the target.
        choices:
          - Do53
          - DoH
          - DoH-FIPS
        type: str
      server_name_indication:
        description:
          - The server name indication for the target.
        type: str
    type: list
  wait:
    description:
      - Whether to wait for the resolver rule state change to complete.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    default: 300
    type: int
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a Route53 Resolver rule is present
  linuxhq.aws.route53_resolver_rule:
    domain_name: cloudflare.com
    name: molecule-cloudflare
    resolver_endpoint_id: rslvr-out-0123456789abcdef0
    rule_type: forward
    tags:
      Name: molecule-cloudflare
    target_ips:
      - ip: 1.1.1.1
        port: 53
      - ip: 1.1.1.2
        port: 53

- name: Ensure a Route53 Resolver rule is absent
  linuxhq.aws.route53_resolver_rule:
    name: molecule-cloudflare
    state: absent
"""

RETURN = r"""
name:
  description:
    - The requested resolver rule name.
  returned: always
  type: str
resolver_rule:
  description:
    - The current resolver rule after module execution.
  returned: when state is present
  type: dict
resolver_rule_id:
  description:
    - The resolver rule ID.
  returned: when a resolver rule exists after module execution
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import json

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
)

ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA = {
    "resolver_rule_complete": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverRule",
        "acceptors": [
            {
                "argument": "ResolverRule.Status",
                "expected": "COMPLETE",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "ResolverRule.Status",
                "expected": "UPDATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverRule.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverRule.Status",
                "expected": "FAILED",
                "matcher": "path",
                "state": "failure",
            },
        ],
    },
    "resolver_rule_deleted": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverRule",
        "acceptors": [
            {
                "expected": "ResourceNotFoundException",
                "matcher": "error",
                "state": "success",
            },
            {
                "argument": "ResolverRule.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}

TARGET_IP_DEFAULTS = {"port": 53, "protocol": "Do53"}
TARGET_IP_FIELDS = (
    "ip",
    "ipv6",
    "port",
    "protocol",
    "server_name_indication",
)


class ResolverRuleWaiterFactory(BaseWaiterFactory):
    @property
    def _waiter_model_data(self):
        return ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA


def apply_tag_deltas(resource, tags_to_set, tag_keys_to_unset):
    updated = dict(resource)
    updated_tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        updated_tags.pop(tag_key, None)
    updated_tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(updated_tags)
    return updated


def create_resolver_rule(client, module, desired):
    try:
        rule = client.create_resolver_rule(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "creator_request_id": desired["name"],
                        "domain_name": desired["domain_name"],
                        "name": desired["name"],
                        "resolver_endpoint_id": desired["resolver_endpoint_id"],
                        "rule_type": desired["rule_type"],
                        "tags": (
                            ansible_dict_to_boto3_tag_list(module.params["tags"])
                            if module.params["tags"] is not None
                            else None
                        ),
                        "target_ips": desired["target_ips"],
                    },
                    capitalize_first=True,
                )
            ),
            aws_retry=True,
        ).get("ResolverRule")
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to create AWS Route53 Resolver rule {desired['name']}"
        )

    if rule is not None and module.params["wait"]:
        resolver_rule_id = rule.get("Id")
        rule = wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"complete"},
        )
    return rule


def delete_resolver_rule(client, module, rule):
    resolver_rule_id = rule.get("Id")

    try:
        client.delete_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete AWS Route53 Resolver rule {module.params['name']}",
        )

    if module.params["wait"]:
        wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"deleted"},
        )


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module)
    changed = rule is not None

    if changed and not module.check_mode:
        delete_resolver_rule(client, module, rule)

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    desired = {
        "domain_name": module.params["domain_name"],
        "name": module.params["name"],
        "resolver_endpoint_id": module.params["resolver_endpoint_id"],
        "rule_type": module.params["rule_type"].upper(),
        "target_ips": module.params["target_ips"],
    }
    rule = get_resolver_rule_by_name(client, module)

    comparable_fields = (
        "domain_name",
        "resolver_endpoint_id",
        "rule_type",
        "target_ips",
    )
    current = comparable_rule(rule)
    desired_comparable = comparable_rule(
        {field: desired[field] for field in comparable_fields}
    )
    desired.update(desired_comparable)
    if current is None:
        changed = True
    else:
        changed = current != desired_comparable
    resource_changed = changed
    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((rule or {}).get("Tags", [])),
            tags,
            purge_tags=purge_tags,
        )
    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if changed and module.check_mode:
        rule = dict(rule or {})
        rule.update(snake_dict_to_camel_dict(desired, capitalize_first=True))
        if tags is not None:
            rule = apply_tag_deltas(rule, tags_to_set, tag_keys_to_unset)
    elif current is None:
        rule = create_resolver_rule(client, module, desired)
        rule = resolver_rule_with_tags(client, module, rule)
    elif changed:
        if resource_changed:
            if (
                current["resolver_endpoint_id"]
                != desired_comparable["resolver_endpoint_id"]
                or current["target_ips"] != desired_comparable["target_ips"]
            ):
                config = scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {
                            "name": desired["name"],
                            "resolver_endpoint_id": desired["resolver_endpoint_id"],
                            "target_ips": desired["target_ips"],
                        },
                        capitalize_first=True,
                    )
                )

                try:
                    rule = client.update_resolver_rule(
                        Config=config,
                        ResolverRuleId=rule.get("Id"),
                        aws_retry=True,
                    ).get("ResolverRule")
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to update AWS Route53 Resolver rule "
                            f"{desired['name']}"
                        ),
                    )

                if rule is not None and module.params["wait"]:
                    resolver_rule_id = rule.get("Id")
                    rule = wait_for_resolver_rule_status(
                        client,
                        module,
                        resolver_rule_id,
                        {"complete"},
                    )

                current = comparable_rule(rule)

            if current != desired_comparable:
                if rule is not None:
                    delete_resolver_rule(client, module, rule)
                rule = create_resolver_rule(client, module, desired)
        if rule is not None and tags is not None:
            if resource_changed:
                rule = resolver_rule_with_tags(client, module, rule)
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(rule.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )
            resource_arn = rule.get("Arn")

            if resource_arn:
                if tag_keys_to_unset:
                    try:
                        client.untag_resource(
                            ResourceArn=resource_arn,
                            TagKeys=tag_keys_to_unset,
                            aws_retry=True,
                        )
                    except Exception as e:
                        module.fail_json_aws(
                            e,
                            msg=(
                                "Unable to remove tags from AWS Route53 Resolver "
                                f"rule {resource_arn}"
                            ),
                        )

                if tags_to_set:
                    try:
                        client.tag_resource(
                            ResourceArn=resource_arn,
                            Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                            aws_retry=True,
                        )
                    except Exception as e:
                        module.fail_json_aws(
                            e,
                            msg=(
                                "Unable to tag AWS Route53 Resolver rule "
                                f"{resource_arn}"
                            ),
                        )

            rule = apply_tag_deltas(rule, tags_to_set, tag_keys_to_unset)

    result_rule = boto3_resource_to_ansible_dict(
        rule, transform_tags=True, force_tags=False
    )
    result = {
        "changed": changed,
        "name": desired["name"],
        "resolver_rule": result_rule,
        "state": "present",
    }
    resolver_rule_id = result_rule.get("id")

    if resolver_rule_id is not None:
        result["resolver_rule_id"] = resolver_rule_id

    module.exit_json(**result)


def wait_for_resolver_rule_status(client, module, resolver_rule_id, statuses):
    deleted = "deleted" in statuses

    try:
        waiter = ResolverRuleWaiterFactory().get_waiter(
            client,
            "resolver_rule_deleted" if deleted else "resolver_rule_complete",
        )
        waiter.wait(
            ResolverRuleId=resolver_rule_id,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=module.params["wait_delay"],
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Timed out waiting for AWS Route53 Resolver rule {module.params['name']}",
        )

    if deleted:
        return None
    return get_resolver_rule(client, module, resolver_rule_id)


def comparable_rule(rule):
    if not rule:
        return None
    normalized = boto3_resource_to_ansible_dict(
        rule, transform_tags=False, force_tags=False
    )
    result = {
        "domain_name": normalized.get("domain_name"),
        "resolver_endpoint_id": normalized.get("resolver_endpoint_id"),
        "rule_type": normalized.get("rule_type"),
        "target_ips": comparable_target_ips(normalized.get("target_ips")),
    }
    if result["domain_name"] is not None:
        result["domain_name"] = result["domain_name"].rstrip(".")
    return result


def comparable_target_ips(target_ips):
    normalized = []
    for target_ip in target_ips or []:
        item = dict(TARGET_IP_DEFAULTS)
        item.update(
            {key: value for key, value in target_ip.items() if value is not None}
        )
        normalized.append(
            {
                field: item.get(field)
                for field in TARGET_IP_FIELDS
                if item.get(field) is not None
            }
        )
    return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))


def get_resolver_rule(client, module, resolver_rule_id):
    try:
        rule = client.get_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        ).get("ResolverRule")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule {resolver_rule_id}",
        )

    return resolver_rule_with_tags(client, module, rule)


def get_resolver_rule_by_name(client, module):
    name = module.params["name"]

    try:
        rules = paginated_query_with_retries(
            client,
            "list_resolver_rules",
            Filters=ansible_dict_to_boto3_filter_list({"Name": name}),
        ).get("ResolverRules", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Route53 Resolver rules")

    if len(rules) > 1:
        rule_ids = sorted(rule.get("Id", "") for rule in rules)
        module.fail_json(
            msg=(
                f"Multiple AWS Route53 Resolver rules are named {name}: "
                f"{', '.join(rule_ids)}"
            )
        )

    return get_resolver_rule(client, module, rules[0]["Id"]) if rules else None


def resolver_rule_with_tags(client, module, rule):
    if not rule or not rule.get("Arn"):
        return rule
    rule = dict(rule)

    try:
        rule["Tags"] = paginated_query_with_retries(
            client,
            "list_tags_for_resource",
            ResourceArn=rule["Arn"],
        ).get("Tags", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Route53 Resolver rule {rule['Arn']}",
        )

    return rule


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"type": "str"},
            "name": {"required": True, "type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "resolver_endpoint_id": {"type": "str"},
            "rule_type": {"type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "tags": {"type": "dict"},
            "target_ips": {
                "elements": "dict",
                "mutually_exclusive": [["ip", "ipv6"]],
                "options": {
                    "ip": {"type": "str"},
                    "ipv6": {"type": "str"},
                    "port": {"type": "int"},
                    "protocol": {
                        "choices": ["Do53", "DoH", "DoH-FIPS"],
                        "type": "str",
                    },
                    "server_name_indication": {"type": "str"},
                },
                "type": "list",
            },
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 5, "type": "int"},
            "wait_timeout": {"default": 300, "type": "int"},
        },
        required_if=[
            (
                "state",
                "present",
                ["domain_name", "resolver_endpoint_id", "rule_type", "target_ips"],
            ),
        ],
        supports_check_mode=True,
    )
    state = module.params["state"]
    tags = module.params["tags"]

    if module.params["wait"]:
        if module.params["wait_delay"] < 1:
            module.fail_json(msg="wait_delay must be 1 or greater")

        if module.params["wait_timeout"] < 1:
            module.fail_json(msg="wait_timeout must be 1 or greater")

    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )
    method_names = {"list_resolver_rules"}
    if state == "present":
        method_names.update(
            {
                "create_resolver_rule",
                "delete_resolver_rule",
                "get_resolver_rule",
                "list_tags_for_resource",
                "update_resolver_rule",
            }
        )
        if tags is not None:
            method_names.add("tag_resource")
            if module.params["purge_tags"]:
                method_names.add("untag_resource")
    elif state == "absent":
        method_names.add("delete_resolver_rule")
        if module.params["wait"]:
            method_names.add("get_resolver_rule")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=(
                    "Installed botocore does not support Route53 Resolver "
                    f"{method_name}"
                )
            )

    required_method_parameters = {
        "create_resolver_rule": {
            "CreatorRequestId",
            "DomainName",
            "Name",
            "ResolverEndpointId",
            "RuleType",
            "Tags",
            "TargetIps",
        },
        "delete_resolver_rule": {"ResolverRuleId"},
        "get_resolver_rule": {"ResolverRuleId"},
        "list_resolver_rules": {"Filters", "MaxResults", "NextToken"},
        "list_tags_for_resource": {"MaxResults", "NextToken", "ResourceArn"},
        "tag_resource": {"ResourceArn", "Tags"},
        "untag_resource": {"ResourceArn", "TagKeys"},
        "update_resolver_rule": {"Config", "ResolverRuleId"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Route53 Resolver "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
