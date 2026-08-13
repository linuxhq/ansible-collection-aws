#!/usr/bin/python
# Copyright: Ansible Project
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
    choices:
      - forward
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
      - This must contain at most 200 entries; keys must contain 1 to 128 characters and values at most 256 characters.
    type: dict
  target_ips:
    description:
      - The target IP definitions for forwarding rules.
      - This is required when O(state=present).
      - This must contain at least one entry.
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
          - This must be between C(0) and C(65535).
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

import hashlib
import ipaddress
import json
import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_arn_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
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


def create_resolver_rule(client, module, desired):
    try:
        rule = client.create_resolver_rule(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "creator_request_id": hashlib.sha256(
                            json.dumps(desired, sort_keys=True).encode()
                        ).hexdigest(),
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
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e, msg=f"Unable to create AWS Route53 Resolver rule {desired['name']}"
        )

    if not (rule or {}).get("Id"):
        module.fail_json(
            msg=(
                "AWS Route53 Resolver did not return the created rule "
                f"{desired['name']}"
            )
        )

    if module.params["wait"]:
        resolver_rule_id = rule.get("Id")
        rule = wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"complete"},
        )
    elif rule is not None and module.params["tags"] is not None:
        rule = dict(rule)
        rule["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
    return rule


def delete_resolver_rule(client, module, rule, always=False):
    resolver_rule_id = rule.get("Id")

    try:
        client.delete_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete AWS Route53 Resolver rule {module.params['name']}",
        )

    if module.params["wait"] or always:
        wait_for_resolver_rule_status(
            client,
            module,
            resolver_rule_id,
            {"deleted"},
        )


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module)
    deleting = (rule or {}).get("Status") == "DELETING"
    changed = rule is not None and not deleting

    if deleting and module.params["wait"] and not module.check_mode:
        wait_for_resolver_rule_status(client, module, rule.get("Id"), {"deleted"})
    elif changed and not module.check_mode:
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
    if rule is not None and rule.get("Status") == "DELETING":
        if module.check_mode:
            rule = None
        else:
            wait_for_resolver_rule_status(client, module, rule.get("Id"), {"deleted"})
            return ensure_present(client, module)

    comparable_fields = (
        "domain_name",
        "resolver_endpoint_id",
        "rule_type",
        "target_ips",
    )
    current = comparable_rule(rule)
    created = current is None
    desired_comparable = comparable_rule(
        {field: desired[field] for field in comparable_fields}
    )
    desired.update(desired_comparable)
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

    if (
        changed
        and not module.check_mode
        and rule is not None
        and rule.get("Status")
        and rule.get("Status") != "COMPLETE"
    ):
        wait_for_resolver_rule_status(client, module, rule.get("Id"), {"complete"})
        return ensure_present(client, module)

    if changed and module.check_mode:
        rule = dict(rule or {})
        rule.update(snake_dict_to_camel_dict(desired, capitalize_first=True))
        if tags is not None:
            rule = apply_tag_deltas(rule, tags_to_set, tag_keys_to_unset)
    elif current is None:
        rule = create_resolver_rule(client, module, desired)
        if module.params["wait"]:
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
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to update AWS Route53 Resolver rule "
                            f"{desired['name']}"
                        ),
                    )

                if not (rule or {}).get("Id"):
                    module.fail_json(
                        msg=(
                            "AWS Route53 Resolver did not return the updated rule "
                            f"{desired['name']}"
                        )
                    )

                if module.params["wait"]:
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
                    delete_resolver_rule(client, module, rule, always=True)
                rule = create_resolver_rule(client, module, desired)
                created = True
        if rule is not None and tags is not None:
            if resource_changed and not created:
                rule = resolver_rule_with_tags(client, module, rule)
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(rule.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )
            resource_arn = rule.get("Arn")

            if resource_arn:
                reconcile_arn_tags(
                    module,
                    client,
                    resource_arn,
                    tags_to_set,
                    tag_keys_to_unset,
                    "AWS Route53 Resolver rule",
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

    run_waiter(
        module,
        client,
        ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA,
        "resolver_rule_deleted" if deleted else "resolver_rule_complete",
        f"Timed out waiting for AWS Route53 Resolver rule {module.params['name']}",
        ResolverRuleId=resolver_rule_id,
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
        result["domain_name"] = result["domain_name"].rstrip(".").lower()
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
    unique = {json.dumps(item, sort_keys=True): item for item in normalized}
    return [unique[key] for key in sorted(unique)]


def get_resolver_rule(client, module, resolver_rule_id):
    try:
        rule = client.get_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        ).get("ResolverRule")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule {resolver_rule_id}",
        )

    return resolver_rule_with_tags(client, module, rule)


def get_resolver_rule_by_name(client, module):
    name = module.params["name"]

    rules = query_list(
        module,
        client,
        "list_resolver_rules",
        "ResolverRules",
        "Unable to list AWS Route53 Resolver rules",
        Filters=ansible_dict_to_boto3_filter_list({"Name": name}),
    )

    if len(rules) > 1:
        rule_ids = sorted(rule.get("Id", "") for rule in rules)
        module.fail_json(
            msg=(
                f"Multiple AWS Route53 Resolver rules are named {name}: "
                f"{', '.join(rule_ids)}"
            )
        )

    if not rules:
        return None
    if module.params["state"] == "absent":
        return rules[0]
    return get_resolver_rule(client, module, rules[0]["Id"])


def resolver_rule_with_tags(client, module, rule):
    if not rule or not rule.get("Arn"):
        return rule
    rule = dict(rule)

    rule["Tags"] = query_list(
        module,
        client,
        "list_tags_for_resource",
        "Tags",
        f"Unable to list tags for AWS Route53 Resolver rule {rule['Arn']}",
        ResourceArn=rule["Arn"],
    )

    return rule


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"type": "str"},
            "name": {"required": True, "type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "resolver_endpoint_id": {"type": "str"},
            "rule_type": {"choices": ["forward"], "type": "str"},
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
                "required_one_of": [["ip", "ipv6"]],
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
    name = module.params["name"]

    if (
        len(name) > 64
        or name.isdigit()
        or re.fullmatch(r"[a-zA-Z0-9\-_ ']+", name) is None
    ):
        module.fail_json(
            msg="name must be a valid resolver rule name of at most 64 characters"
        )

    if state == "present":
        if not 1 <= len(module.params["domain_name"]) <= 256:
            module.fail_json(msg="domain_name must contain 1 to 256 characters")
        if not 1 <= len(module.params["resolver_endpoint_id"]) <= 64:
            module.fail_json(msg="resolver_endpoint_id must contain 1 to 64 characters")
        if not module.params["target_ips"]:
            module.fail_json(msg="target_ips must contain at least one entry")
        require_valid_tags(module, tags, 200)

    for target_ip in module.params["target_ips"] or []:
        if target_ip["port"] is not None and not 0 <= target_ip["port"] <= 65535:
            module.fail_json(msg="target_ips[].port must be between 0 and 65535")
        for field, version in (("ip", 4), ("ipv6", 6)):
            value = target_ip.get(field)
            if value is None:
                continue
            try:
                valid = ipaddress.ip_address(value).version == version
            except ValueError:
                valid = False
            if not valid:
                module.fail_json(
                    msg=f"target_ips[].{field} must be a valid IPv{version} address"
                )
        if len(target_ip.get("server_name_indication") or "") > 255:
            module.fail_json(
                msg="target_ips[].server_name_indication must contain at most 255 characters"
            )

    require_positive_wait_bounds(module, always=state == "present")

    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )
    methods = {"list_resolver_rules": ("Filters", "MaxResults", "NextToken")}
    if state == "present":
        create_parameters = (
            "CreatorRequestId",
            "DomainName",
            "Name",
            "ResolverEndpointId",
            "RuleType",
            "TargetIps",
        )
        if tags is not None:
            create_parameters += ("Tags",)
        methods["create_resolver_rule"] = create_parameters
        methods["delete_resolver_rule"] = ("ResolverRuleId",)
        methods["get_resolver_rule"] = ("ResolverRuleId",)
        methods["list_tags_for_resource"] = ("MaxResults", "NextToken", "ResourceArn")
        methods["update_resolver_rule"] = ("Config", "ResolverRuleId")
        if tags:
            methods["tag_resource"] = ("ResourceArn", "Tags")
        if tags is not None and module.params["purge_tags"]:
            methods["untag_resource"] = ("ResourceArn", "TagKeys")

    if state == "absent":
        methods["delete_resolver_rule"] = ("ResolverRuleId",)
        if module.params["wait"]:
            methods["get_resolver_rule"] = ("ResolverRuleId",)

    require_client_methods(module, client, "Route53 Resolver", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
