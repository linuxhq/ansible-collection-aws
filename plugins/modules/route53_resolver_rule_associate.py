#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_resolver_rule_associate
short_description: Manage aws route53 resolver rule associations
description:
  - Manages AWS Route53 Resolver rule associations.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The resolver rule association name.
      - This must be a nonnumeric name of at most 64 letters, numbers, spaces,
        apostrophes, hyphens, or underscores.
      - Changing the name of an existing association disassociates and
        reassociates the resolver rule.
      - This is required when O(state=present).
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
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Ensure a Route53 Resolver rule association is present
  linuxhq.aws.route53_resolver_rule_associate:
    name: molecule-1
    resolver_rule_id: rslvr-rr-0123456789abcdef0
    vpc_id: vpc-0123456789abcdef0

- name: Ensure a Route53 Resolver rule association is absent
  linuxhq.aws.route53_resolver_rule_associate:
    resolver_rule_id: rslvr-rr-0123456789abcdef0
    state: absent
    vpc_id: vpc-0123456789abcdef0
"""

RETURN = r"""
name:
  description:
    - The requested resolver rule association name.
  returned: when provided
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

import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
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
                "expected": "OVERRIDDEN",
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
                "expected": "DELETING",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "ResolverRuleAssociation.Status",
                "expected": "FAILED",
                "matcher": "path",
                "state": "failure",
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
    name = module.params.get("name")
    association = get_resolver_rule_association_by_rule_and_vpc(client, module)
    deleting = (association or {}).get("Status") == "DELETING"
    changed = association is not None and not deleting
    resolver_rule_association_id = (association or {}).get("Id")

    if association is not None and not module.check_mode:
        if changed:
            try:
                client.disassociate_resolver_rule(
                    ResolverRuleId=module.params["resolver_rule_id"],
                    VPCId=module.params["vpc_id"],
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                pass
            except (BotoCoreError, ClientError) as e:
                identifier = f"{module.params['resolver_rule_id']}/{module.params['vpc_id']}"
                module.fail_json_aws(
                    e,
                    msg=("Unable to delete AWS Route53 Resolver rule association " f"{identifier}"),
                )

        if module.params["wait"]:
            wait_for_resolver_rule_association_status(
                client,
                module,
                resolver_rule_association_id,
                {"deleted"},
            )

    result = {"changed": changed, "state": "absent"}
    if name is not None:
        result["name"] = name
    module.exit_json(**result)


def ensure_present(client, module):
    name = module.params["name"]
    resolver_rule_id = module.params["resolver_rule_id"]
    vpc_id = module.params["vpc_id"]
    association = get_resolver_rule_association_by_rule_and_vpc(client, module)
    if association is not None and association.get("Status") == "DELETING":
        if module.check_mode:
            association = None
        else:
            wait_for_resolver_rule_association_status(client, module, association.get("Id"), {"deleted"})
            return ensure_present(client, module)
    current_association = (
        {
            "name": association.get("Name"),
            "resolver_rule_id": association.get("ResolverRuleId"),
            "vpc_id": association.get("VPCId"),
        }
        if association
        else None
    )
    desired_association = {
        "name": name,
        "resolver_rule_id": resolver_rule_id,
        "vpc_id": vpc_id,
    }
    changed = (current_association or {}) != desired_association

    if (
        changed
        and not module.check_mode
        and association is not None
        and association.get("Status")
        and association.get("Status") not in ("COMPLETE", "OVERRIDDEN")
    ):
        wait_for_resolver_rule_association_status(client, module, association.get("Id"), {"complete"})
        return ensure_present(client, module)

    if changed and not module.check_mode:
        if association is not None:
            resolver_rule_association_id = association.get("Id")

            try:
                client.disassociate_resolver_rule(
                    ResolverRuleId=resolver_rule_id,
                    VPCId=vpc_id,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                pass
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=("Unable to replace AWS Route53 Resolver rule association " f"{name}"),
                )

            wait_for_resolver_rule_association_status(
                client,
                module,
                resolver_rule_association_id,
                {"deleted"},
            )

        try:
            response = client.associate_resolver_rule(
                Name=name,
                ResolverRuleId=resolver_rule_id,
                VPCId=vpc_id,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 Resolver rule association {name}",
            )

        association = response.get("ResolverRuleAssociation") if isinstance(response, dict) else None
        if not isinstance(association, dict) or not association.get("Id"):
            association = get_resolver_rule_association_by_rule_and_vpc(client, module)
        if association is None:
            module.fail_json(msg=("AWS Route53 Resolver did not return the created rule " f"association {name}"))
        association = validate_resolver_rule_association(module, association, "associate_resolver_rule")

        if module.params["wait"]:
            resolver_rule_association_id = association.get("Id")
            association = wait_for_resolver_rule_association_status(
                client,
                module,
                resolver_rule_association_id,
                {"complete"},
            )
    elif changed and module.check_mode:
        association = {
            "Name": name,
            "ResolverRuleId": resolver_rule_id,
            "VPCId": vpc_id,
        }

    result = {
        "changed": changed,
        "name": name,
        "resolver_rule_association": boto3_resource_to_ansible_dict(
            association, transform_tags=False, force_tags=False
        ),
        "state": "present",
    }

    resolver_rule_association_id = (association or {}).get("Id")

    if resolver_rule_association_id is not None:
        result["resolver_rule_association_id"] = resolver_rule_association_id

    module.exit_json(**result)


def wait_for_resolver_rule_association_status(client, module, resolver_rule_association_id, statuses):
    deleted = "deleted" in statuses
    identifier = module.params.get("name") or (f"{module.params['resolver_rule_id']}/{module.params['vpc_id']}")

    run_waiter(
        module,
        client,
        ROUTE53_RESOLVER_RULE_ASSOCIATION_WAITER_MODEL_DATA,
        ("resolver_rule_association_deleted" if deleted else "resolver_rule_association_complete"),
        ("Timed out waiting for AWS Route53 Resolver rule association " f"{identifier}"),
        ResolverRuleAssociationId=resolver_rule_association_id,
    )

    if deleted:
        return None

    try:
        response = client.get_resolver_rule_association(
            ResolverRuleAssociationId=resolver_rule_association_id,
            aws_retry=True,
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        module.fail_json(
            msg=(
                "AWS Route53 Resolver did not return rule association "
                f"{resolver_rule_association_id} after waiting for it to become complete"
            )
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=("Unable to get AWS Route53 Resolver rule association " f"{resolver_rule_association_id}"),
        )

    association = response.get("ResolverRuleAssociation") if isinstance(response, dict) else None
    return validate_resolver_rule_association(
        module,
        association,
        "get_resolver_rule_association",
        expected_id=resolver_rule_association_id,
    )


def get_resolver_rule_association_by_rule_and_vpc(client, module):
    resolver_rule_id = module.params["resolver_rule_id"]
    vpc_id = module.params["vpc_id"]

    associations = query_list(
        module,
        client,
        "list_resolver_rule_associations",
        "ResolverRuleAssociations",
        "Unable to list AWS Route53 Resolver rule associations for " f"{resolver_rule_id}/{vpc_id}",
        Filters=ansible_dict_to_boto3_filter_list(
            {
                "ResolverRuleId": resolver_rule_id,
                "VPCId": vpc_id,
            }
        ),
    )

    associations = [
        validate_resolver_rule_association(
            module,
            association,
            "list_resolver_rule_associations",
            expected_resolver_rule_id=resolver_rule_id,
            expected_vpc_id=vpc_id,
        )
        for association in associations
    ]

    if len(associations) > 1:
        association_ids = sorted(association["Id"] for association in associations)
        module.fail_json(
            msg=(
                "Multiple AWS Route53 Resolver rule associations exist for "
                f"{resolver_rule_id}/{vpc_id}: {', '.join(association_ids)}"
            )
        )

    return associations[0] if associations else None


def validate_resolver_rule_association(
    module,
    association,
    operation,
    expected_id=None,
    expected_resolver_rule_id=None,
    expected_vpc_id=None,
):
    if not isinstance(association, dict):
        module.fail_json(msg=f"{operation}: AWS returned an invalid resolver rule association")

    association_id = association.get("Id")
    if not isinstance(association_id, str) or not association_id:
        module.fail_json(msg=f"{operation}: AWS returned a resolver rule association without a valid ID")
    if expected_id is not None and association_id != expected_id:
        module.fail_json(msg=f"{operation}: AWS returned an unexpected resolver rule association ID {association_id}")

    expected_fields = {
        "ResolverRuleId": expected_resolver_rule_id,
        "VPCId": expected_vpc_id,
    }
    for field, expected_value in expected_fields.items():
        if expected_value is not None and association.get(field) != expected_value:
            module.fail_json(msg=f"{operation}: AWS returned an unexpected resolver rule association {field}")

    for field in ("Name", "ResolverRuleId", "Status", "VPCId"):
        if field in association and not isinstance(association[field], str):
            module.fail_json(msg=f"{operation}: AWS returned an invalid resolver rule association {field}")

    return association


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
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
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    state = module.params["state"]

    if state == "present":
        name = module.params["name"]
        if len(name) > 64 or name.isdigit() or re.fullmatch(r"[a-zA-Z0-9\-_ ']+", name) is None:
            module.fail_json(msg="name must be a valid resolver rule association name of at most 64 characters")

    require_positive_wait_bounds(module, always=state == "present")

    client = module.client("route53resolver", retry_decorator=AWSRetry.jittered_backoff())
    methods = {
        "list_resolver_rule_associations": ("Filters", "MaxResults", "NextToken"),
    }
    if state == "present":
        methods["associate_resolver_rule"] = ("Name", "ResolverRuleId", "VPCId")
        methods["disassociate_resolver_rule"] = ("ResolverRuleId", "VPCId")
        methods["get_resolver_rule_association"] = ("ResolverRuleAssociationId",)

    if state == "absent":
        methods["disassociate_resolver_rule"] = ("ResolverRuleId", "VPCId")
        if module.params["wait"]:
            methods["get_resolver_rule_association"] = ("ResolverRuleAssociationId",)

    require_client_methods(module, client, "Route53 Resolver", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
