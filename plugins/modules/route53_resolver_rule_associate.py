#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule_associate
version_added: 1.9.1
short_description: Manage AWS Route53 Resolver rule associations
description:
  - Manages AWS Route53 Resolver rule associations.
  - O(name) is immutable after association creation.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The resolver rule association name.
    required: true
    type: str
  resolver_rule_id:
    description:
      - The resolver rule ID to associate.
    required: true
    type: str
  state:
    description:
      - Whether the resolver rule association should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  vpc_id:
    description:
      - The VPC ID to associate with the resolver rule.
    required: true
    type: str
  wait:
    description:
      - Whether to wait for the resolver rule association state change to complete.
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
- name: Ensure a Route53 Resolver rule association is present
  linuxhq.aws.route53_resolver_rule_associate:
    name: molecule-1
    resolver_rule_id: rslvr-rr-0123456789abcdef0
    vpc_id: vpc-0123456789abcdef0

- name: Ensure a Route53 Resolver rule association is absent
  linuxhq.aws.route53_resolver_rule_associate:
    name: molecule-1
    resolver_rule_id: rslvr-rr-0123456789abcdef0
    state: absent
    vpc_id: vpc-0123456789abcdef0
"""

RETURN = r"""
name:
  description:
    - The requested resolver rule association name.
  returned: always
  type: str
resolver_rule_association:
  description:
    - The current resolver rule association after module execution.
  returned: when state is present
  type: dict
resolver_rule_association_id:
  description:
    - The resolver rule association ID.
  returned: when an association exists after module execution
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    validate_immutable_fields,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.route53_resolver import (
    get_resolver_rule_association_by_rule_and_vpc,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    wait_for_aws_resource,
)

ROUTE53_RESOLVER_RULE_ASSOCIATION_WAITER_MODEL_DATA = {
    "resolver_rule_association_complete": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverRuleAssociation",
        "acceptors": [
            {
                "argument": "ResolverRuleAssociation.Status",
                "expected": "COMPLETE",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "ResolverRuleAssociation.Status",
                "expected": "CREATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverRuleAssociation.Status",
                "expected": "UPDATING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverRuleAssociation.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
    "resolver_rule_association_deleted": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "GetResolverRuleAssociation",
        "acceptors": [
            {
                "expected": "ResourceNotFoundException",
                "matcher": "error",
                "state": "success",
            },
            {
                "argument": "ResolverRuleAssociation.Status",
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}


def ensure_absent(client, module):
    association = get_resolver_rule_association_by_rule_and_vpc(
        client, module, module.params["resolver_rule_id"], module.params["vpc_id"]
    )
    changed = association is not None

    if changed and not module.check_mode:
        resolver_rule_association_id = association["Id"]
        aws_response(
            client,
            module,
            "disassociate_resolver_rule",
            error_message=(
                "Unable to delete AWS Route53 Resolver rule association "
                f"{module.params['name']}"
            ),
            ResolverRuleId=module.params["resolver_rule_id"],
            VPCId=module.params["vpc_id"],
        )
        if module.params["wait"]:
            wait_for_resolver_rule_association_status(
                client,
                module,
                resolver_rule_association_id,
                {"deleted"},
                module.params["name"],
            )

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    association = get_resolver_rule_association_by_rule_and_vpc(
        client, module, module.params["resolver_rule_id"], module.params["vpc_id"]
    )
    validate_immutable_fields(
        module,
        association,
        {"name": module.params["name"]},
        ["name"],
        (
            "Unable to update AWS Route53 Resolver rule association "
            f"{module.params['name']}: immutable fields differ"
        ),
    )

    changed = association is None

    if changed and not module.check_mode:
        association = aws_resource(
            client,
            module,
            "associate_resolver_rule",
            "ResolverRuleAssociation",
            error_message=(
                "Unable to create AWS Route53 Resolver rule association "
                f"{module.params['name']}"
            ),
            Name=module.params["name"],
            ResolverRuleId=module.params["resolver_rule_id"],
            VPCId=module.params["vpc_id"],
        )
        if module.params["wait"]:
            association = wait_for_resolver_rule_association_status(
                client,
                module,
                association["Id"],
                {"complete"},
                module.params["name"],
            )
    elif changed and module.check_mode:
        association = {"Name": module.params["name"]}

    result = {
        "changed": changed,
        "name": module.params["name"],
        "resolver_rule_association": aws_resource_to_snake_dict(association),
        "state": "present",
    }
    if association is not None and association.get("Id") is not None:
        result["resolver_rule_association_id"] = association["Id"]

    module.exit_json(**result)


def wait_for_resolver_rule_association_status(
    client, module, resolver_rule_association_id, statuses, name
):
    deleted = "deleted" in statuses
    wait_for_aws_resource(
        client,
        module,
        ROUTE53_RESOLVER_RULE_ASSOCIATION_WAITER_MODEL_DATA,
        (
            "resolver_rule_association_deleted"
            if deleted
            else "resolver_rule_association_complete"
        ),
        f"Timed out waiting for AWS Route53 Resolver rule association {name}",
        ResolverRuleAssociationId=resolver_rule_association_id,
    )
    if deleted:
        return None
    return aws_resource(
        client,
        module,
        "get_resolver_rule_association",
        "ResolverRuleAssociation",
        ignore_error_codes="ResourceNotFoundException",
        ignored_error_result=None,
        ResolverRuleAssociationId=resolver_rule_association_id,
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"required": True, "type": "str"},
            "resolver_rule_id": {"required": True, "type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "vpc_id": {"required": True, "type": "str"},
            "wait": {"default": True, "type": "bool"},
            "wait_delay": {"default": 5, "type": "int"},
            "wait_timeout": {"default": 300, "type": "int"},
        },
        supports_check_mode=True,
    )
    client = module.client("route53resolver")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
