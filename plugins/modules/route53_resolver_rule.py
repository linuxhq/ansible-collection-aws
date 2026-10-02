#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule
version_added: '1.9.0'
short_description: Manage aws route53 resolver rules
description:
  - Manages AWS Route53 Resolver rules.
  - Updates resolver endpoint and target IP settings for existing rules.
  - Changes to the domain name or rule type fail without modifying the existing rule.
  - Existing rules are deleted only with O(state=absent).
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
notes:
  - O(tags) accepts at most 200 entries; keys must contain 1 to 128 characters
    and values at most 256 characters.
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
  contains:
    arn:
      description: The rule ARN.
      returned: always
      type: str
    creation_time:
      description: The time the rule was created.
      returned: when returned by AWS
      type: str
    domain_name:
      description: The rule domain name.
      returned: always
      type: str
    id:
      description: The rule ID.
      returned: always
      type: str
    name:
      description: The rule name.
      returned: when configured
      type: str
    owner_id:
      description: The account that owns the rule.
      returned: always
      type: str
    resolver_endpoint_id:
      description: The outbound resolver endpoint ID.
      returned: for forward rules
      type: str
    rule_type:
      description: The rule type.
      returned: always
      type: str
      sample: FORWARD
    share_status:
      description: Whether the rule is shared.
      returned: always
      type: str
    status:
      description: The rule status.
      returned: always
      type: str
      sample: COMPLETE
    status_message:
      description: Details about the rule status.
      returned: when returned by AWS
      type: str
    tags:
      description: The rule tags with key case preserved.
      returned: when gathered by the module
      type: dict
    target_ips:
      description: The rule target IPs.
      returned: for forward rules
      type: list
      elements: dict
      contains:
        ip:
          description: The IPv4 target address.
          returned: when configured
          type: str
        ipv6:
          description: The IPv6 target address.
          returned: when configured
          type: str
        port:
          description: The target port.
          returned: when returned by AWS
          type: int
        protocol:
          description: The target protocol.
          returned: when returned by AWS
          type: str
        server_name_indication:
          description: The target server name indication.
          returned: when configured
          type: str
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
                "state": "failure",
            },
            # FAILED is final; wait_for_resolver_rule_status reports it with the AWS status message.
            {
                "argument": "ResolverRule.Status",
                "expected": "FAILED",
                "matcher": "path",
                "state": "success",
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

TARGET_IP_FIELDS = (
    "ip",
    "ipv6",
    "port",
    "protocol",
    "server_name_indication",
)
# The OwnerId of rules that Route 53 Resolver creates, such as the Internet Resolver rule.
AWS_OWNED_RULE_OWNER = "Route 53 Resolver"


def desired_request(module):
    # The request uses the values as supplied; normalization is only for comparison.
    return {
        "DomainName": module.params["domain_name"],
        "Name": module.params["name"],
        "ResolverEndpointId": module.params["resolver_endpoint_id"],
        "RuleType": module.params["rule_type"].upper(),
        "TargetIps": [
            snake_dict_to_camel_dict(scrub_none_parameters(target_ip), capitalize_first=True)
            for target_ip in module.params["target_ips"]
        ],
    }


def create_resolver_rule(client, module, request):
    try:
        response = client.create_resolver_rule(
            **request,
            CreatorRequestId=hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest(),
            **(
                {"Tags": ansible_dict_to_boto3_tag_list(module.params["tags"])}
                if module.params["tags"] is not None
                else {}
            ),
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to create AWS Route53 Resolver rule {request['Name']}")

    rule = response.get("ResolverRule") if isinstance(response, dict) else None
    if not isinstance(rule, dict) or not rule.get("Id"):
        rule = get_resolver_rule_by_name(client, module)

    if rule is None:
        module.fail_json(msg=f"AWS Route53 Resolver did not return the created rule {request['Name']}")

    rule = validate_resolver_rule(module, rule, "create_resolver_rule")

    if module.params["wait"]:
        return wait_for_resolver_rule_status(client, module, rule["Id"], "complete")

    rule = dict(rule)
    for field, value in request.items():
        rule.setdefault(field, value)

    return rule


def delete_resolver_rule(client, module, rule):
    resolver_rule_id = rule.get("Id")

    try:
        client.delete_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return
    except is_boto3_error_code("ResourceInUseException") as e:
        module.fail_json_aws(
            e,
            msg=(
                f"Unable to delete AWS Route53 Resolver rule {module.params['name']}: "
                "it is still associated with VPCs; remove its associations first"
            ),
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to delete AWS Route53 Resolver rule {module.params['name']}",
        )

    if module.params["wait"]:
        wait_for_resolver_rule_status(client, module, resolver_rule_id, "deleted")


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module)
    deleting = (rule or {}).get("Status") == "DELETING"
    changed = rule is not None and not deleting

    if deleting and module.params["wait"] and not module.check_mode:
        wait_for_resolver_rule_status(client, module, rule.get("Id"), "deleted")
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
    request = desired_request(module)
    desired = comparable_rule(request)

    rule = get_resolver_rule_by_name(client, module)
    if rule is not None and rule.get("Status") == "DELETING":
        if module.check_mode:
            rule = None
        else:
            wait_for_resolver_rule_status(client, module, rule["Id"], "deleted")
            return ensure_present(client, module)

    # Updates do not change tags, so later reads reuse these.
    current_tags = (rule or {}).get("Tags", [])
    current = comparable_rule(rule)
    failed = (rule or {}).get("Status") == "FAILED"
    # A FAILED rule is repaired by sending the desired configuration again.
    resource_changed = current is None or failed or not rules_match(current, desired)

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict(current_tags),
            tags,
            purge_tags=purge_tags,
        )

    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if (
        (changed or module.params["wait"])
        and not module.check_mode
        and rule is not None
        and rule.get("Status")
        and rule.get("Status") not in ("COMPLETE", "FAILED")
    ):
        wait_for_resolver_rule_status(client, module, rule["Id"], "complete", allow_failed=True)
        return ensure_present(client, module)

    if current is not None:
        immutable_changes = [field for field in ("domain_name", "rule_type") if current[field] != desired[field]]
        if immutable_changes:
            module.fail_json(
                msg=(
                    f"{', '.join(immutable_changes)} cannot be changed for an existing AWS Route53 Resolver rule. "
                    "The existing rule has not been modified."
                )
            )

    if changed and module.check_mode:
        # Only a configuration change replaces the stored values; a tag-only change keeps them.
        rule = dict(rule or {}, **request) if resource_changed else dict(rule)
        if tags is not None:
            rule = apply_tag_deltas(dict(rule, Tags=current_tags), tags_to_set, tag_keys_to_unset)
    elif current is None:
        rule = create_resolver_rule(client, module, request)
        if module.params["wait"]:
            rule = resolver_rule_with_tags(client, module, rule)
        elif tags is not None:
            rule["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    elif changed:
        resolver_rule_id = rule["Id"]
        if resource_changed:
            config = {field: request[field] for field in ("Name", "ResolverEndpointId", "TargetIps")}
            try:
                response = client.update_resolver_rule(
                    Config=config,
                    ResolverRuleId=resolver_rule_id,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to update AWS Route53 Resolver rule {request['Name']}")

            rule = response.get("ResolverRule") if isinstance(response, dict) else None
            if isinstance(rule, dict) and rule.get("Id"):
                rule = validate_resolver_rule(module, rule, "update_resolver_rule", expected_id=resolver_rule_id)

            if not resolver_rule_has_details(rule):
                rule = get_resolver_rule(client, module, resolver_rule_id)

            if rule is None:
                module.fail_json(msg=f"AWS Route53 Resolver did not return the updated rule {request['Name']}")

            if module.params["wait"]:
                rule = wait_for_resolver_rule_status(client, module, resolver_rule_id, "complete")

            if not rules_match(comparable_rule(rule), desired):
                module.fail_json(
                    msg=(
                        "AWS Route53 Resolver rule does not match the requested configuration after updating. "
                        "The rule has not been deleted; inspect the current configuration before retrying."
                    ),
                    current=comparable_rule(rule),
                    desired=desired,
                )

        rule = dict(rule, Tags=rule.get("Tags", current_tags))
        if tags is not None:
            if tags_to_set or tag_keys_to_unset:
                resource_arn = rule.get("Arn")
                if not isinstance(resource_arn, str) or not resource_arn:
                    module.fail_json(
                        msg=(
                            "Unable to reconcile tags for AWS Route53 Resolver rule "
                            f"{request['Name']}: AWS returned an invalid rule ARN"
                        )
                    )

                reconcile_arn_tags(
                    module,
                    client,
                    resource_arn,
                    tags_to_set,
                    tag_keys_to_unset,
                    "AWS Route53 Resolver rule",
                )

            rule = apply_tag_deltas(rule, tags_to_set, tag_keys_to_unset)

    result_rule = boto3_resource_to_ansible_dict(rule, transform_tags=True, force_tags=False)
    result = {
        "changed": changed,
        "name": request["Name"],
        "resolver_rule": result_rule,
        "state": "present",
    }
    resolver_rule_id = result_rule.get("id")

    if resolver_rule_id is not None:
        result["resolver_rule_id"] = resolver_rule_id

    module.exit_json(**result)


def wait_for_resolver_rule_status(client, module, resolver_rule_id, state, allow_failed=False):
    # The waiter fails on terminal states as well as on timeouts, so the message names neither.
    run_waiter(
        module,
        client,
        ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA,
        f"resolver_rule_{state}",
        f"Unable to wait for AWS Route53 Resolver rule {module.params['name']} to become {state}",
        ResolverRuleId=resolver_rule_id,
    )

    if state == "deleted":
        return None

    rule = get_resolver_rule(client, module, resolver_rule_id)
    if rule is not None and rule.get("Status") == "FAILED" and not allow_failed:
        module.fail_json(
            msg=(
                f"AWS Route53 Resolver rule {module.params['name']} failed: "
                f"{rule.get('StatusMessage') or 'no status message was returned'}"
            ),
            resolver_rule=boto3_resource_to_ansible_dict(rule, transform_tags=False, force_tags=False),
        )

    return rule


def comparable_target_ip(target_ip):
    normalized = boto3_resource_to_ansible_dict(target_ip, transform_tags=False, force_tags=False)
    for field in ("ip", "ipv6"):
        if normalized.get(field) is not None:
            try:
                normalized[field] = str(ipaddress.ip_address(normalized[field]))
            except ValueError:
                pass

    return {field: normalized[field] for field in TARGET_IP_FIELDS if normalized.get(field) is not None}


def comparable_rule(rule):
    if not rule:
        return None

    domain_name = rule.get("DomainName")
    return {
        # Domain names are case-insensitive and AWS returns them with a trailing dot.
        "domain_name": domain_name.rstrip(".").lower() if isinstance(domain_name, str) else domain_name,
        "resolver_endpoint_id": rule.get("ResolverEndpointId"),
        "rule_type": rule.get("RuleType"),
        "target_ips": sorted(
            (comparable_target_ip(target_ip) for target_ip in rule.get("TargetIps") or []),
            key=lambda item: json.dumps(item, sort_keys=True),
        ),
    }


def target_ips_match(current, desired):
    # A requested target matches a current one when every supplied field is equal; omitted fields keep AWS values.
    remaining = list(current)
    for desired_target_ip in sorted(desired, key=len, reverse=True):
        match = next(
            (
                index
                for index, current_target_ip in enumerate(remaining)
                if all(current_target_ip.get(field) == value for field, value in desired_target_ip.items())
            ),
            None,
        )
        if match is None:
            return False

        remaining.pop(match)

    return not remaining


def rules_match(current, desired):
    if current is None:
        return False

    return all(
        current[field] == desired[field] for field in ("domain_name", "resolver_endpoint_id", "rule_type")
    ) and target_ips_match(current["target_ips"], desired["target_ips"])


def get_resolver_rule(client, module, resolver_rule_id):
    try:
        response = client.get_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule {resolver_rule_id}",
        )

    rule = response.get("ResolverRule") if isinstance(response, dict) else None
    return validate_resolver_rule(
        module,
        rule,
        "get_resolver_rule",
        expected_id=resolver_rule_id,
        require_details=True,
    )


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

    rules = [validate_resolver_rule(module, rule, "list_resolver_rules", expected_name=name) for rule in rules]
    # Only rules this account owns can be managed; skip rules shared from other accounts and AWS-owned rules.
    rules = [
        rule
        for rule in rules
        if rule.get("ShareStatus") != "SHARED_WITH_ME" and rule.get("OwnerId") != AWS_OWNED_RULE_OWNER
    ]

    if len(rules) > 1:
        rule_ids = sorted(rule["Id"] for rule in rules)
        module.fail_json(msg=f"Multiple AWS Route53 Resolver rules are named {name}: {', '.join(rule_ids)}")

    if not rules:
        return None

    if module.params["state"] == "absent":
        return rules[0]

    # ListResolverRules returns the full rule, so only the tags need another call.
    rule = validate_resolver_rule(module, rules[0], "list_resolver_rules", require_details=True)
    return resolver_rule_with_tags(client, module, rule)


def resolver_rule_with_tags(client, module, rule):
    if not rule or not rule.get("Arn"):
        return rule

    rule = dict(rule)

    tags = query_list(
        module,
        client,
        "list_tags_for_resource",
        "Tags",
        f"Unable to list tags for AWS Route53 Resolver rule {rule['Arn']}",
        ResourceArn=rule["Arn"],
    )
    rule["Tags"] = validate_tags(module, tags)

    return rule


def resolver_rule_has_details(rule):
    return isinstance(rule, dict) and all(
        field in rule for field in ("DomainName", "ResolverEndpointId", "RuleType", "TargetIps")
    )


def validate_resolver_rule(
    module,
    rule,
    operation,
    expected_id=None,
    expected_name=None,
    require_details=False,
):
    if not isinstance(rule, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid resolver rule")

    rule_id = rule.get("Id")
    if not isinstance(rule_id, str) or not rule_id:
        module.fail_json(msg=f"{operation}: AWS returned a resolver rule without a valid ID")

    if expected_id is not None and rule_id != expected_id:
        module.fail_json(msg=f"{operation}: AWS returned an unexpected resolver rule ID {rule_id}")

    if expected_name is not None and rule.get("Name") != expected_name:
        module.fail_json(msg=f"{operation}: AWS returned an unexpected resolver rule name")

    for field in ("Arn", "DomainName", "Name", "ResolverEndpointId", "RuleType", "Status"):
        if field in rule and not isinstance(rule[field], str):
            module.fail_json(msg=f"{operation}: AWS returned an invalid resolver rule {field}")

    if require_details and not resolver_rule_has_details(rule):
        module.fail_json(msg=f"{operation}: AWS returned an incomplete resolver rule")

    if "TargetIps" in rule:
        validate_target_ips(module, rule["TargetIps"], operation)

    return rule


def validate_target_ips(module, target_ips, operation):
    if not isinstance(target_ips, list):
        module.fail_json(msg=f"{operation}: AWS returned an invalid resolver rule TargetIps")

    for target_ip in target_ips:
        if not isinstance(target_ip, dict):
            module.fail_json(msg=f"{operation}: AWS returned an invalid target IP")

        if not any(isinstance(target_ip.get(field), str) and target_ip[field] for field in ("Ip", "Ipv6")):
            module.fail_json(msg=f"{operation}: AWS returned a target IP without an IP address")

        for field in ("Ip", "Ipv6", "Protocol", "ServerNameIndication"):
            if field in target_ip and not isinstance(target_ip[field], str):
                module.fail_json(msg=f"{operation}: AWS returned an invalid target IP {field}")

        if "Port" in target_ip and (not isinstance(target_ip["Port"], int) or isinstance(target_ip["Port"], bool)):
            module.fail_json(msg=f"{operation}: AWS returned an invalid target IP Port")

    return target_ips


def validate_tags(module, tags):
    for tag in tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str):
            module.fail_json(msg="list_tags_for_resource: AWS returned an invalid tag")

    return tags


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
            "tags": {"aliases": ["resource_tags"], "type": "dict"},
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

    if len(name) > 64 or name.isdigit() or re.fullmatch(r"[a-zA-Z0-9\-_ ']+", name) is None:
        module.fail_json(msg="name must be a valid resolver rule name of at most 64 characters")

    if state == "present":
        if not 1 <= len(module.params["domain_name"]) <= 256:
            module.fail_json(msg="domain_name must contain 1 to 256 characters")

        if not 1 <= len(module.params["resolver_endpoint_id"]) <= 64:
            module.fail_json(msg="resolver_endpoint_id must contain 1 to 64 characters")

        if not module.params["target_ips"]:
            module.fail_json(msg="target_ips must contain at least one entry")

        normalized_targets = [
            json.dumps(
                comparable_target_ip(snake_dict_to_camel_dict(scrub_none_parameters(target_ip), capitalize_first=True)),
                sort_keys=True,
            )
            for target_ip in module.params["target_ips"]
        ]
        if len(set(normalized_targets)) != len(normalized_targets):
            module.fail_json(msg="target_ips entries must be unique")

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
                module.fail_json(msg=f"target_ips[].{field} must be a valid IPv{version} address")

        if len(target_ip.get("server_name_indication") or "") > 255:
            module.fail_json(msg="target_ips[].server_name_indication must contain at most 255 characters")

    require_positive_wait_bounds(module, always=state == "present")

    client = module.client("route53resolver", retry_decorator=AWSRetry.jittered_backoff())
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
