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

import time
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.route53 import (
    list_resolver_rules,
    normalize_resolver_rule,
)


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


def get_resolver_rule(client, module, resolver_rule_id):
    get_resolver_rule = AWSRetry.jittered_backoff()(client.get_resolver_rule)
    try:
        response = get_resolver_rule(ResolverRuleId=resolver_rule_id)
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule {resolver_rule_id}",
        )
    return response.get("ResolverRule")


def get_resolver_rule_by_name(client, module, name):
    for rule in list_resolver_rules(client, module):
        if rule.get("Name") == name:
            return rule
    return None


def wait_for_resolver_rule_status(client, module, resolver_rule_id, statuses, name):
    deadline = time.time() + module.params["wait_timeout"]

    while time.time() < deadline:
        rule = get_resolver_rule(client, module, resolver_rule_id)
        if rule is None and "deleted" in statuses:
            return None
        if rule is not None and rule.get("Status", "").lower() in statuses:
            return rule
        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=f"Timed out waiting for AWS Route53 Resolver rule {name}",
        resolver_rule_id=resolver_rule_id,
    )


def ensure_present(client, module):
    rule = get_resolver_rule_by_name(client, module, module.params["name"])
    changed = rule is None

    if changed and not module.check_mode:
        create_resolver_rule = AWSRetry.jittered_backoff()(client.create_resolver_rule)
        try:
            response = create_resolver_rule(
                CreatorRequestId=module.params["name"],
                DomainName=module.params["domain_name"],
                Name=module.params["name"],
                ResolverEndpointId=module.params["resolver_endpoint_id"],
                RuleType=module.params["rule_type"].upper(),
                TargetIps=aws_target_ips(module.params["target_ips"]),
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 Resolver rule {module.params['name']}",
            )
        rule = response.get("ResolverRule")
        if module.params["wait"]:
            rule = wait_for_resolver_rule_status(
                client, module, rule["Id"], {"complete"}, module.params["name"]
            )
    elif changed and module.check_mode:
        rule = {"Name": module.params["name"]}

    result = {
        "changed": changed,
        "name": module.params["name"],
        "resolver_rule": normalize_resolver_rule(rule),
        "state": "present",
    }
    if rule is not None and rule.get("Id") is not None:
        result["resolver_rule_id"] = rule["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    rule = get_resolver_rule_by_name(client, module, module.params["name"])
    changed = rule is not None

    if changed and not module.check_mode:
        resolver_rule_id = rule["Id"]
        delete_resolver_rule = AWSRetry.jittered_backoff()(client.delete_resolver_rule)
        try:
            delete_resolver_rule(ResolverRuleId=resolver_rule_id)
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
