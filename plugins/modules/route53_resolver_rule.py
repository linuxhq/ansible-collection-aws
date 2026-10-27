#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule
version_added: '1.9.0'
short_description: Manage AWS Route53 resolver rules
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
      - This must contain 1 to 256 characters.
    type: str
  name:
    description:
      - The resolver rule name.
      - This must be a nonnumeric name of at most 64 letters, numbers, spaces,
        apostrophes, hyphens, or underscores.
    required: true
    type: str
  resolver_endpoint_id:
    description:
      - The resolver endpoint ID for the rule.
      - This is required when O(state=present).
      - This must contain 1 to 64 characters.
    type: str
  rule_type:
    description:
      - The resolver rule type.
      - Only V(FORWARD) rules can be managed by this module; C(SYSTEM),
        C(RECURSIVE), and C(DELEGATE) rules are not supported.
      - This is required when O(state=present).
    choices:
      - FORWARD
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
          - O(target_ips[].ip) or O(target_ips[].ipv6) is required.
          - Mutually exclusive with O(target_ips[].ipv6).
        type: str
      ipv6:
        description:
          - The IPv6 address of the target.
          - O(target_ips[].ip) or O(target_ips[].ipv6) is required.
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
          - This must contain at most 255 characters.
          - This requires botocore C(1.35.38) or later.
        type: str
    type: list
  wait:
    description:
      - Whether to wait for the resolver rule state change to complete.
      - Even when O(wait=false), when O(state=present) the module waits for a C(DELETING) rule to be
        deleted before creating it again, and for a rule that is still changing to settle before
        updating it. These waits use O(wait_delay) and are bounded by O(wait_timeout).
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true) or while the module waits even when
        O(wait=false).
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - Also bounds the waits that happen even when O(wait=false).
      - Sequential waits in one run share this budget.
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
    rule_type: FORWARD
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
      returned: except when check mode predicts creation
      type: str
    creation_time:
      description: The time the rule was created.
      returned: when returned by AWS
      type: str
    creator_request_id:
      description: The unique string that identifies the request that created the rule.
      returned: when returned by AWS
      type: str
    domain_name:
      description: The rule domain name.
      returned: always
      type: str
    id:
      description: The rule ID.
      returned: except when check mode predicts creation
      type: str
    modification_time:
      description: The time the rule was last modified.
      returned: when returned by AWS
      type: str
    name:
      description: The rule name.
      returned: when configured
      type: str
    owner_id:
      description: The account that owns the rule.
      returned: except when check mode predicts creation
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
      returned: except when check mode predicts creation
      type: str
    status:
      description: The rule status.
      returned: except when check mode predicts creation
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

import json
import uuid

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

from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    AWS_OWNED_RULE_OWNER,
    comparable_ip_fields,
    comparable_ips_match,
    comparable_ips_matches,
    reconcile_resolver_arn_tags,
    require_ip_versions,
    resolver_resource_with_tags,
    resolver_rule_has_details,
    valid_resolver_name,
    validate_resolver_rule,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    require_resulting_tag_limit,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    custom_waiter,
    require_positive_wait_bounds,
    run_waiter,
    wait_deadline,
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
# Ports AWS stores for a target sent without one, used only to predict check-mode results.
# Outbound endpoints do not support DoH-FIPS, so no DoH-FIPS target can exist.
TARGET_DEFAULT_PORTS = {"Do53": 53, "DoH": 443}


def desired_request(module):
    # The request uses the values as supplied; normalization is only for comparison.
    return {
        "DomainName": module.params["domain_name"],
        "Name": module.params["name"],
        "ResolverEndpointId": module.params["resolver_endpoint_id"],
        "RuleType": module.params["rule_type"],
        "TargetIps": [
            snake_dict_to_camel_dict(scrub_none_parameters(target_ip), capitalize_first=True)
            for target_ip in module.params["target_ips"]
        ],
    }


def create_resolver_rule(client, module, request, deadline=None):
    try:
        response = client.create_resolver_rule(
            **request,
            CreatorRequestId=str(uuid.uuid4()),
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
        rule = get_resolver_rule_by_name(client, module, changed=True)

    if rule is None:
        module.fail_json(changed=True, msg=f"AWS Route53 Resolver did not return the created rule {request['Name']}")

    rule = validate_resolver_rule(module, rule, "create_resolver_rule", changed=True)

    if module.params["wait"]:
        return wait_for_resolver_rule_status(client, module, rule["Id"], "complete", changed=True, deadline=deadline)

    rule = dict(rule)
    for field, value in request.items():
        rule.setdefault(field, value)

    return rule


def delete_resolver_rule(client, module, rule, deadline=None):
    resolver_rule_id = rule.get("Id")

    try:
        client.delete_resolver_rule(
            ResolverRuleId=resolver_rule_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return False
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
        wait_for_resolver_rule_status(client, module, resolver_rule_id, "deleted", changed=True, deadline=deadline)

    return True


def ensure_absent(client, module):
    deadline = wait_deadline(module)
    rule = get_resolver_rule_by_name(client, module)
    if rule is not None and rule.get("RuleType", "FORWARD") != "FORWARD":
        module.fail_json(
            changed=False,
            msg=(
                f"AWS Route53 Resolver rule {module.params['name']} ({rule['Id']}) is a {rule['RuleType']} rule; "
                "only FORWARD rules can be managed. The existing rule has not been modified."
            ),
        )

    deleting = (rule or {}).get("Status") == "DELETING"
    changed = rule is not None and not deleting

    if deleting and module.params["wait"] and not module.check_mode:
        wait_for_resolver_rule_status(client, module, rule.get("Id"), "deleted", deadline=deadline)
    elif changed and not module.check_mode:
        changed = delete_resolver_rule(client, module, rule, deadline=deadline)

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module, deadline=None):
    # Re-runs after a wait pass the deadline on, so every wait in one run shares wait_timeout.
    if deadline is None:
        deadline = wait_deadline(module)

    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    request = desired_request(module)
    desired = comparable_rule(request)

    rule = get_resolver_rule_by_name(client, module)
    if rule is not None and rule.get("Status") == "DELETING":
        if module.check_mode:
            rule = None
        else:
            wait_for_resolver_rule_status(client, module, rule["Id"], "deleted", deadline=deadline)
            return ensure_present(client, module, deadline=deadline)

    # Updates do not change tags, so later reads reuse these.
    current_tags = (rule or {}).get("Tags", [])
    current = comparable_rule(rule)
    failed = (rule or {}).get("Status") == "FAILED"
    # A FAILED rule is repaired by sending the desired configuration again.
    resource_changed = current is None or failed or not rules_match(current, desired)

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        current_tag_dict = boto3_tag_list_to_ansible_dict(current_tags)
        tags_to_set, tag_keys_to_unset = compare_aws_tags(current_tag_dict, tags, purge_tags=purge_tags)
        require_resulting_tag_limit(
            module, current_tag_dict, tags_to_set, tag_keys_to_unset, 200, "AWS Route53 Resolver rule"
        )

    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if (
        (changed or module.params["wait"])
        and rule is not None
        and rule.get("Status")
        and rule.get("Status") not in ("COMPLETE", "FAILED")
    ):
        if not module.check_mode:
            wait_for_resolver_rule_status(client, module, rule["Id"], "complete", allow_failed=True, deadline=deadline)
            return ensure_present(client, module, deadline=deadline)

        # A real run first waits for the rule to settle.
        rule = dict(rule, Status="COMPLETE")

    if current is not None:
        immutable_changes = [field for field in ("domain_name", "rule_type") if current[field] != desired[field]]
        if immutable_changes:
            module.fail_json(
                msg=(
                    f"{', '.join(immutable_changes)} cannot be changed for an existing AWS Route53 Resolver rule. "
                    "The existing rule has not been modified."
                )
            )

    if current is not None and resource_changed:
        # UpdateResolverRule resets omitted target fields, so keep the values of the matched current targets.
        request = dict(request, TargetIps=target_ips_with_current_fields(rule["TargetIps"], request["TargetIps"]))

    if changed and module.check_mode:
        if rule is None:
            # AWS stores the domain name lowercased with a trailing dot.
            rule = dict(
                request,
                DomainName=request["DomainName"].rstrip(".").lower() + ".",
                TargetIps=target_ips_with_aws_defaults(request["TargetIps"]),
            )
        elif resource_changed:
            # UpdateResolverRule changes only its Config fields; domain_name and rule_type already match.
            rule = dict(
                rule,
                Name=request["Name"],
                ResolverEndpointId=request["ResolverEndpointId"],
                TargetIps=target_ips_with_aws_defaults(request["TargetIps"]),
            )
        else:
            # A tag-only change keeps the stored values.
            rule = dict(rule)

        # A waited create lists the new rule's tags.
        if tags is not None or (current is None and module.params["wait"]):
            rule = apply_tag_deltas(dict(rule, Tags=current_tags), tags_to_set, tag_keys_to_unset)
    elif current is None:
        rule = create_resolver_rule(client, module, request, deadline=deadline)
        if module.params["wait"]:
            rule = resolver_resource_with_tags(client, module, rule, "rule", changed=True)
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
                rule = validate_resolver_rule(
                    module, rule, "update_resolver_rule", expected_id=resolver_rule_id, changed=True
                )

            if not resolver_rule_has_details(rule):
                rule = get_resolver_rule(client, module, resolver_rule_id, changed=True)

            if rule is None:
                module.fail_json(
                    changed=True,
                    msg=f"AWS Route53 Resolver did not return the updated rule {request['Name']}",
                )

            if module.params["wait"]:
                rule = wait_for_resolver_rule_status(
                    client, module, resolver_rule_id, "complete", changed=True, deadline=deadline
                )

            current = comparable_rule(rule)
            if not rules_match(current, desired):
                module.fail_json(
                    msg=(
                        "AWS Route53 Resolver rule does not match the requested configuration after updating. "
                        "The rule has not been deleted; inspect the current configuration before retrying."
                    ),
                    changed=True,
                    current=current,
                    desired=desired,
                )

        rule = dict(rule, Tags=rule.get("Tags", current_tags))
        if tags is not None:
            reconcile_resolver_arn_tags(
                module,
                client,
                rule,
                "rule",
                request["Name"],
                tags_to_set,
                tag_keys_to_unset,
                changed=resource_changed,
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


def wait_for_resolver_rule_status(
    client, module, resolver_rule_id, state, allow_failed=False, changed=False, deadline=None
):
    """Wait for a rule status; changed reports whether the rule was already modified.

    deadline limits the wait to what is left of the run's shared wait_timeout budget.
    """
    # The waiter fails on terminal states as well as on timeouts, so the message names neither.
    error_msg = f"Unable to wait for AWS Route53 Resolver rule {module.params['name']} to become {state}"
    run_waiter(
        module,
        custom_waiter(client, ROUTE53_RESOLVER_RULE_WAITER_MODEL_DATA, f"resolver_rule_{state}"),
        error_msg,
        changed=changed,
        deadline=deadline,
        ResolverRuleId=resolver_rule_id,
    )

    if state == "deleted":
        return None

    rule = get_resolver_rule(client, module, resolver_rule_id, changed=changed)
    if rule is not None and rule.get("Status") == "FAILED" and not allow_failed:
        module.fail_json(
            changed=changed,
            msg=(
                f"AWS Route53 Resolver rule {module.params['name']} failed: "
                f"{rule.get('StatusMessage') or 'no status message was returned'}"
            ),
            resolver_rule=boto3_resource_to_ansible_dict(rule, transform_tags=False, force_tags=False),
        )

    return rule


def target_ips_with_current_fields(current_target_ips, target_ips):
    """Fill omitted port, protocol, and SNI of each target from the current target it matches."""
    matches = comparable_ips_matches(
        [comparable_target_ip(target_ip) for target_ip in current_target_ips],
        [comparable_target_ip(target_ip) for target_ip in target_ips],
    )
    return [
        (
            target_ip
            if match is None
            else dict(
                {
                    field: current_target_ips[match][field]
                    for field in ("Port", "Protocol", "ServerNameIndication")
                    if current_target_ips[match].get(field) is not None
                },
                **target_ip,
            )
        )
        for target_ip, match in zip(target_ips, matches)
    ]


def target_ips_with_aws_defaults(target_ips):
    """Fill the values AWS stores for an omitted protocol (Do53) and an omitted port (53 for Do53, 443 for DoH).

    AWS stores an empty server name indication as no value, so it is dropped.
    """
    predicted = []
    for target_ip in target_ips:
        target_ip = dict(target_ip)
        if target_ip.get("ServerNameIndication") == "":
            del target_ip["ServerNameIndication"]

        target_ip.setdefault("Protocol", "Do53")
        if target_ip["Protocol"] in TARGET_DEFAULT_PORTS:
            target_ip.setdefault("Port", TARGET_DEFAULT_PORTS[target_ip["Protocol"]])

        predicted.append(target_ip)

    return predicted


def comparable_target_ip(target_ip):
    return comparable_ip_fields(target_ip, TARGET_IP_FIELDS)


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


def rules_match(current, desired):
    if current is None:
        return False

    return all(
        current[field] == desired[field] for field in ("domain_name", "resolver_endpoint_id", "rule_type")
    ) and comparable_ips_match(current["target_ips"], desired["target_ips"])


def get_resolver_rule(client, module, resolver_rule_id, changed=False):
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
            changed=changed,
            msg=f"Unable to get AWS Route53 Resolver rule {resolver_rule_id}",
        )

    rule = response.get("ResolverRule") if isinstance(response, dict) else None
    return validate_resolver_rule(
        module,
        rule,
        "get_resolver_rule",
        expected_id=resolver_rule_id,
        require_details=True,
        changed=changed,
    )


def get_resolver_rule_by_name(client, module, changed=False):
    """Find the rule by name; changed reports whether the rule was already modified, for failure results."""
    name = module.params["name"]

    rules = query_list(
        module,
        client,
        "list_resolver_rules",
        "ResolverRules",
        "Unable to list AWS Route53 Resolver rules",
        changed=changed,
        Filters=ansible_dict_to_boto3_filter_list({"Name": name}),
    )

    rules = [
        validate_resolver_rule(module, rule, "list_resolver_rules", expected_name=name, changed=changed)
        for rule in rules
    ]
    # Only rules this account owns can be managed; skip rules shared from other accounts and AWS-owned rules.
    rules = [
        rule
        for rule in rules
        if rule.get("ShareStatus") != "SHARED_WITH_ME" and rule.get("OwnerId") != AWS_OWNED_RULE_OWNER
    ]

    if len(rules) > 1:
        rule_ids = sorted(rule["Id"] for rule in rules)
        module.fail_json(
            changed=changed, msg=f"Multiple AWS Route53 Resolver rules are named {name}: {', '.join(rule_ids)}"
        )

    if not rules:
        return None

    if module.params["state"] == "absent":
        return rules[0]

    # ListResolverRules returns the full rule, so only the tags need another call.
    # Only FORWARD rules have an endpoint and targets; other types reach the immutable rule_type check.
    rule = validate_resolver_rule(
        module,
        rules[0],
        "list_resolver_rules",
        require_details=rules[0].get("RuleType") == "FORWARD",
        changed=changed,
    )
    return resolver_resource_with_tags(client, module, rule, "rule", changed=changed)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"type": "str"},
            "name": {"required": True, "type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "resolver_endpoint_id": {"type": "str"},
            "rule_type": {"choices": ["FORWARD"], "type": "str"},
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

    if not valid_resolver_name(name):
        module.fail_json(msg="name must be a valid resolver rule name of at most 64 characters")

    if state == "present":
        if not 1 <= len(module.params["domain_name"]) <= 256:
            module.fail_json(msg="domain_name must contain 1 to 256 characters")

        if not 1 <= len(module.params["resolver_endpoint_id"]) <= 64:
            module.fail_json(msg="resolver_endpoint_id must contain 1 to 64 characters")

        if not module.params["target_ips"]:
            module.fail_json(msg="target_ips must contain at least one entry")

        normalized_targets = [
            json.dumps(comparable_target_ip(target_ip), sort_keys=True) for target_ip in module.params["target_ips"]
        ]
        if len(set(normalized_targets)) != len(normalized_targets):
            module.fail_json(msg="target_ips entries must be unique")

        require_valid_tags(module, tags, 200)

    for target_ip in module.params["target_ips"] or []:
        # ansible-core counts an explicit null as set for required_one_of.
        if target_ip.get("ip") is None and target_ip.get("ipv6") is None:
            module.fail_json(msg="target_ips entries must set ip or ipv6")

        if target_ip["port"] is not None and not 0 <= target_ip["port"] <= 65535:
            module.fail_json(msg="target_ips[].port must be between 0 and 65535")

        require_ip_versions(module, target_ip, "target_ips")

        if len(target_ip.get("server_name_indication") or "") > 255:
            module.fail_json(msg="target_ips[].server_name_indication must contain at most 255 characters")

    require_positive_wait_bounds(module, always=state == "present")

    if any(target_ip.get("server_name_indication") is not None for target_ip in module.params["target_ips"] or []):
        module.require_botocore_at_least("1.35.38", reason="for target_ips[].server_name_indication")

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
