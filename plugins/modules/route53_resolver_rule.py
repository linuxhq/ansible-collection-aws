#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule
version_added: "1.9.0"
short_description: Manage AWS Route53 Resolver rules
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
        type: str
      ipv6:
        description:
          - The IPv6 address of the target.
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
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
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
    target_ips:
      - ip: 1.1.1.1
        port: 53
      - ip: 1.1.1.2
        port: 53
    tags:
      Name: molecule-cloudflare

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
    recursive_diff,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
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
    if module.params["wait"]:
        resolver_rule_id = rule.get("Id")
        rule = wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"complete"},
            desired["name"],
        )
    return rule


def delete_resolver_rule(client, module, rule, name):
    resolver_rule_id = rule.get("Id")
    try:
        client.delete_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to delete AWS Route53 Resolver rule {name}"
        )
    if module.params["wait"]:
        wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"deleted"},
            name,
        )


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module, module.params["name"])
    changed = rule is not None

    if changed and not module.check_mode:
        delete_resolver_rule(client, module, rule, module.params["name"])

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    desired = {
        "domain_name": module.params["domain_name"],
        "name": module.params["name"],
        "resolver_endpoint_id": module.params["resolver_endpoint_id"],
        "rule_type": module.params["rule_type"].upper(),
        "target_ips": module.params["target_ips"],
    }
    rule = get_resolver_rule_by_name(client, module, desired["name"])

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
        changed = (
            recursive_diff((current) or {}, (desired_comparable) or {}) is not None
        )
    resource_changed = changed
    tags_to_set, tag_keys_to_unset = tag_changes(module, rule)
    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if current is None and not module.check_mode:
        rule = create_resolver_rule(client, module, desired)
        rule = resolver_rule_with_tags(client, module, rule)
    elif current is None and module.check_mode:
        rule = desired
        if module.params["tags"] is not None:
            rule["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
    elif changed and not module.check_mode:
        if resource_changed:
            rule = update_resolver_rule(client, module, rule, desired)
            current = comparable_rule(rule)
            desired_comparable = comparable_rule(
                {field: desired[field] for field in comparable_fields}
            )
            if recursive_diff((current) or {}, (desired_comparable) or {}) is not None:
                delete_resolver_rule(client, module, rule, desired["name"])
                rule = create_resolver_rule(client, module, desired)
        if rule is not None and module.params["tags"] is not None:
            rule = resolver_rule_with_tags(client, module, rule)
            tags_to_set, tag_keys_to_unset = tag_changes(module, rule)
            apply_tag_changes(
                client,
                module,
                rule.get("Arn"),
                tags_to_set,
                tag_keys_to_unset,
            )
            rule = resolver_rule_with_tags(client, module, rule)
    elif changed and module.check_mode:
        rule = desired
        if module.params["tags"] is not None:
            rule["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])

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


def update_resolver_rule(client, module, rule, desired):
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
        updated_rule = client.update_resolver_rule(
            Config=config,
            ResolverRuleId=rule.get("Id"),
            aws_retry=True,
        ).get("ResolverRule")
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to update AWS Route53 Resolver rule {desired['name']}"
        )
    if module.params["wait"]:
        resolver_rule_id = updated_rule.get("Id")
        updated_rule = wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"complete"},
            desired["name"],
        )
    return updated_rule


def tag_changes(module, resource):
    if module.params["tags"] is None:
        return {}, []
    current_tags = boto3_tag_list_to_ansible_dict((resource or {}).get("Tags", []))
    return compare_aws_tags(
        current_tags,
        module.params["tags"],
        purge_tags=module.params["purge_tags"],
    )


def apply_tag_changes(client, module, resource_arn, tags_to_set, tag_keys_to_unset):
    if not resource_arn:
        return
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
                msg=f"Unable to remove tags from AWS Route53 Resolver rule {resource_arn}",
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
                msg=f"Unable to tag AWS Route53 Resolver rule {resource_arn}",
            )


def wait_for_resolver_rule_status(client, module, resolver_rule_id, statuses, name):
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
                default_pause=max(1, module.params["wait_delay"]),
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Timed out waiting for AWS Route53 Resolver rule {name}"
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


def get_resolver_rule_by_name(client, module, name):
    rule = next(
        (
            rule
            for rule in paginated_query_with_retries(client, "list_resolver_rules").get(
                "ResolverRules", []
            )
            if rule.get("Name") == name
        ),
        None,
    )
    if rule is None:
        return None
    return get_resolver_rule(client, module, rule["Id"])


def resolver_rule_with_tags(client, module, rule):
    if not rule or not rule.get("Arn"):
        return rule
    rule = dict(rule)
    try:
        rule["Tags"] = client.list_tags_for_resource(
            ResourceArn=rule["Arn"],
            aws_retry=True,
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
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
