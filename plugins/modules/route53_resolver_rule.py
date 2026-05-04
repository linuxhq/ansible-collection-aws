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
      - The target IP definitions in AWS format.
      - This is required when O(state=present).
    elements: dict
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
      - Ip: 1.1.1.1
        Port: 53
      - Ip: 1.1.1.2
        Port: 53

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

import time

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in (
        "ResourceNotFoundException",
    )


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


def get_resolver_rule_by_name(client, module):
    for rule in list_resolver_rules(client, module):
        if rule.get("Name") == module.params["name"]:
            return rule
    return None


def get_resolver_rule(client, module, resolver_rule_id):
    try:
        response = client.get_resolver_rule(ResolverRuleId=resolver_rule_id)
    except Exception as e:
        if is_not_found_error(e):
            return None
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule {resolver_rule_id}",
        )
    return response.get("ResolverRule")


def wait_for_status(client, module, resolver_rule_id, statuses):
    deadline = time.time() + module.params["wait_timeout"]

    while time.time() < deadline:
        rule = get_resolver_rule(client, module, resolver_rule_id)
        if rule is None and "deleted" in statuses:
            return None
        if rule is not None and rule.get("Status", "").lower() in statuses:
            return rule
        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=f"Timed out waiting for AWS Route53 Resolver rule {module.params['name']}",
        resolver_rule_id=resolver_rule_id,
    )


def normalize(rule):
    if rule is None:
        return None
    normalized = camel_dict_to_snake_dict(rule)
    if "target_ips" in normalized:
        normalized["target_ips"] = rule.get("TargetIps", [])
    return normalized


def ensure_present(client, module):
    rule = get_resolver_rule_by_name(client, module)
    changed = rule is None

    if changed and not module.check_mode:
        try:
            response = client.create_resolver_rule(
                CreatorRequestId=module.params["name"],
                DomainName=module.params["domain_name"],
                Name=module.params["name"],
                ResolverEndpointId=module.params["resolver_endpoint_id"],
                RuleType=module.params["rule_type"].upper(),
                TargetIps=module.params["target_ips"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 Resolver rule {module.params['name']}",
            )
        rule = response.get("ResolverRule")
        if module.params["wait"]:
            rule = wait_for_status(client, module, rule["Id"], {"complete"})
    elif changed and module.check_mode:
        rule = {"Name": module.params["name"]}

    result = {
        "changed": changed,
        "name": module.params["name"],
        "resolver_rule": normalize(rule),
        "state": "present",
    }
    if rule is not None and rule.get("Id") is not None:
        result["resolver_rule_id"] = rule["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module)
    changed = rule is not None

    if changed and not module.check_mode:
        resolver_rule_id = rule["Id"]
        try:
            client.delete_resolver_rule(ResolverRuleId=resolver_rule_id)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 Resolver rule {module.params['name']}",
            )
        if module.params["wait"]:
            wait_for_status(client, module, resolver_rule_id, {"deleted"})

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
