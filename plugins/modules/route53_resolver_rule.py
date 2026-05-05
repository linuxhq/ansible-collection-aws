#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule
version_added: 1.9.1
short_description: Manage AWS Route53 Resolver rules
description:
  - Manages AWS Route53 Resolver rules.
  - Updates resolver endpoint and target IP settings for existing rules.
  - O(domain_name) and O(rule_type) are immutable after creation.
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
    canonicalize_list,
    find_aws_resource,
    validated_field_differences,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    wait_for_aws_resource,
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

IMMUTABLE_ITEMS = ["domain_name", "rule_type"]
COMPARE_ITEMS = [
    "domain_name",
    "resolver_endpoint_id",
    "rule_type",
    "target_ips",
]


def aws_target_ip(target_ip):
    return scrub_none_parameters(
        {
            "Ip": target_ip.get("ip"),
            "Ipv6": target_ip.get("ipv6"),
            "Port": target_ip.get("port"),
            "Protocol": target_ip.get("protocol"),
            "ServerNameIndication": target_ip.get("server_name_indication"),
        }
    )


def aws_target_ips(target_ips):
    return [aws_target_ip(target_ip) for target_ip in target_ips]


def build_desired_resolver_rule(module):
    return {
        "domain_name": module.params["domain_name"],
        "name": module.params["name"],
        "resolver_endpoint_id": module.params["resolver_endpoint_id"],
        "rule_type": module.params["rule_type"].upper(),
        "target_ips": module.params["target_ips"],
    }


def normalize_target_ip(target_ip):
    return scrub_none_parameters(
        {
            "ip": target_ip.get("ip"),
            "ipv6": target_ip.get("ipv6"),
            "port": target_ip.get("port") or 53,
            "protocol": target_ip.get("protocol"),
            "server_name_indication": target_ip.get("server_name_indication"),
        }
    )


def target_ip_sort_key(target_ip):
    return (
        target_ip.get("ip") or "",
        target_ip.get("ipv6") or "",
        target_ip.get("port") or 0,
        target_ip.get("protocol") or "",
        target_ip.get("server_name_indication") or "",
    )


def normalize_target_ips(target_ips):
    return canonicalize_list(
        target_ips,
        normalize_target_ip,
        target_ip_sort_key,
    )


def comparable_resolver_rule(rule):
    if not rule:
        return None
    return {
        "domain_name": rule.get("domain_name", "").rstrip("."),
        "resolver_endpoint_id": rule.get("resolver_endpoint_id"),
        "rule_type": rule.get("rule_type"),
        "target_ips": normalize_target_ips(rule.get("target_ips")),
    }


def comparable_desired_resolver_rule(desired):
    return {
        "domain_name": desired["domain_name"].rstrip("."),
        "resolver_endpoint_id": desired["resolver_endpoint_id"],
        "rule_type": desired["rule_type"],
        "target_ips": normalize_target_ips(desired["target_ips"]),
    }


def get_resolver_rule(client, module, resolver_rule_id):
    return aws_resource(
        client,
        module,
        "get_resolver_rule",
        "ResolverRule",
        ignore_error_codes="ResourceNotFoundException",
        ignored_error_result=None,
        ResolverRuleId=resolver_rule_id,
    )


def get_resolver_rule_by_name(client, module, name):
    return find_aws_resource(
        aws_paginated_list(
            client,
            module,
            "list_resolver_rules",
            "ResolverRules",
        ),
        name=name,
    )


def wait_for_resolver_rule_status(client, module, resolver_rule_id, statuses, name):
    deleted = "deleted" in statuses
    wait_for_aws_resource(
        client,
        module,
        ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA,
        "resolver_rule_deleted" if deleted else "resolver_rule_complete",
        f"Timed out waiting for AWS Route53 Resolver rule {name}",
        ResolverRuleId=resolver_rule_id,
    )
    if deleted:
        return None
    return get_resolver_rule(client, module, resolver_rule_id)


def create_resolver_rule(client, module, desired):
    response = aws_response(
        client,
        module,
        "create_resolver_rule",
        error_message=f"Unable to create AWS Route53 Resolver rule {desired['name']}",
        CreatorRequestId=desired["name"],
        DomainName=desired["domain_name"],
        Name=desired["name"],
        ResolverEndpointId=desired["resolver_endpoint_id"],
        RuleType=desired["rule_type"],
        TargetIps=aws_target_ips(desired["target_ips"]),
    )
    rule = response.get("ResolverRule")
    if module.params["wait"]:
        rule = wait_for_resolver_rule_status(
            client, module, rule["Id"], {"complete"}, desired["name"]
        )
    return rule


def update_resolver_rule(client, module, rule, desired):
    response = aws_response(
        client,
        module,
        "update_resolver_rule",
        error_message=f"Unable to update AWS Route53 Resolver rule {desired['name']}",
        ResolverRuleId=rule["id"],
        Config=scrub_none_parameters(
            {
                "Name": desired["name"],
                "ResolverEndpointId": desired["resolver_endpoint_id"],
                "TargetIps": aws_target_ips(desired["target_ips"]),
            }
        ),
    )
    updated_rule = response.get("ResolverRule")
    if module.params["wait"]:
        updated_rule = wait_for_resolver_rule_status(
            client, module, updated_rule["Id"], {"complete"}, desired["name"]
        )
    return updated_rule


def ensure_present(client, module):
    desired = build_desired_resolver_rule(module)
    rule = get_resolver_rule_by_name(client, module, desired["name"])
    if rule is not None:
        rule = aws_resource_to_snake_dict(rule)

    current = comparable_resolver_rule(rule)
    desired_comparable = comparable_desired_resolver_rule(desired)
    if current is None:
        changed = True
    else:
        differences, changed = validated_field_differences(
            module,
            current,
            desired_comparable,
            COMPARE_ITEMS,
            IMMUTABLE_ITEMS,
            (
                "Unable to update AWS Route53 Resolver rule "
                f"{module.params['name']}: immutable fields differ"
            ),
        )

    if current is None and not module.check_mode:
        rule = aws_resource_to_snake_dict(create_resolver_rule(client, module, desired))
    elif current is None and module.check_mode:
        rule = desired
    elif changed and not module.check_mode:
        rule = aws_resource_to_snake_dict(
            update_resolver_rule(client, module, rule, desired)
        )
    elif changed and module.check_mode:
        rule = desired

    result = {
        "changed": changed,
        "name": desired["name"],
        "resolver_rule": rule,
        "state": "present",
    }
    if rule is not None and rule.get("id") is not None:
        result["resolver_rule_id"] = rule["id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module, module.params["name"])
    changed = rule is not None

    if changed and not module.check_mode:
        resolver_rule_id = rule["Id"]
        aws_response(
            client,
            module,
            "delete_resolver_rule",
            error_message=f"Unable to delete AWS Route53 Resolver rule {module.params['name']}",
            ResolverRuleId=resolver_rule_id,
        )
        if module.params["wait"]:
            wait_for_resolver_rule_status(
                client,
                module,
                resolver_rule_id,
                {"deleted"},
                module.params["name"],
            )

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"type": "str"},
            "name": {"required": True, "type": "str"},
            "resolver_endpoint_id": {"type": "str"},
            "rule_type": {"type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
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
    client = module.client("route53resolver")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
