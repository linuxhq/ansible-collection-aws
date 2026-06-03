#!/usr/bin/python
# Copyright: Taylor Kimball
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_to_ansible_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
    custom_waiter_config,
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


class ResolverRuleAssociationWaiterFactory(BaseWaiterFactory):
    @property
    def _waiter_model_data(self):
        return ROUTE53_RESOLVER_RULE_ASSOCIATION_WAITER_MODEL_DATA


def ensure_absent(client, module):
    name = module.params["name"]
    association = get_resolver_rule_association_by_rule_and_vpc(client, module)
    changed = association is not None
    resolver_rule_association_id = (association or {}).get("Id")

    if changed and not module.check_mode:
        try:
            client.disassociate_resolver_rule(
                ResolverRuleId=module.params["resolver_rule_id"],
                VPCId=module.params["vpc_id"],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 Resolver rule association {name}",
            )

        if module.params["wait"]:
            wait_for_resolver_rule_association_status(
                client,
                module,
                resolver_rule_association_id,
                {"deleted"},
            )

    module.exit_json(
        changed=changed,
        name=name,
        state="absent",
    )


def ensure_present(client, module):
    name = module.params["name"]
    resolver_rule_id = module.params["resolver_rule_id"]
    vpc_id = module.params["vpc_id"]
    association = get_resolver_rule_association_by_rule_and_vpc(client, module)
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

    if changed and not module.check_mode:
        if association is not None:
            resolver_rule_association_id = association.get("Id")
            try:
                client.disassociate_resolver_rule(
                    ResolverRuleId=resolver_rule_id,
                    VPCId=vpc_id,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to replace AWS Route53 Resolver rule association "
                        f"{name}"
                    ),
                )

            if module.params["wait"]:
                wait_for_resolver_rule_association_status(
                    client,
                    module,
                    resolver_rule_association_id,
                    {"deleted"},
                )

        try:
            association = client.associate_resolver_rule(
                Name=name,
                ResolverRuleId=resolver_rule_id,
                VPCId=vpc_id,
                aws_retry=True,
            ).get("ResolverRuleAssociation")
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 Resolver rule association {name}",
            )

        if module.params["wait"]:
            resolver_rule_association_id = association.get("Id")
            association = wait_for_resolver_rule_association_status(
                client,
                module,
                resolver_rule_association_id,
                {"complete"},
            )
    elif changed and module.check_mode:
        association = desired_association

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


def wait_for_resolver_rule_association_status(
    client, module, resolver_rule_association_id, statuses
):
    name = module.params["name"]
    deleted = "deleted" in statuses
    try:
        waiter = ResolverRuleAssociationWaiterFactory().get_waiter(
            client,
            (
                "resolver_rule_association_deleted"
                if deleted
                else "resolver_rule_association_complete"
            ),
        )
        waiter.wait(
            ResolverRuleAssociationId=resolver_rule_association_id,
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=max(1, module.params["wait_delay"]),
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Timed out waiting for AWS Route53 Resolver rule association {name}",
        )

    if deleted:
        return None

    try:
        return client.get_resolver_rule_association(
            ResolverRuleAssociationId=resolver_rule_association_id,
            aws_retry=True,
        ).get("ResolverRuleAssociation")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to get AWS Route53 Resolver rule association "
                f"{resolver_rule_association_id}"
            ),
        )


def get_resolver_rule_association_by_rule_and_vpc(client, module):
    resolver_rule_id = module.params["resolver_rule_id"]
    vpc_id = module.params["vpc_id"]
    try:
        associations = paginated_query_with_retries(
            client,
            "list_resolver_rule_associations",
            Filters=ansible_dict_to_boto3_filter_list(
                {
                    "ResolverRuleId": resolver_rule_id,
                    "VPCId": vpc_id,
                }
            ),
        ).get("ResolverRuleAssociations", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list AWS Route53 Resolver rule associations for "
                f"{resolver_rule_id}/{vpc_id}"
            ),
        )
    for association in associations:
        if association.get("ResolverRuleId") != resolver_rule_id:
            continue

        if association.get("VPCId") != vpc_id:
            continue

        return association

    return None


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
    client = module.client(
        "route53resolver", retry_decorator=AWSRetry.jittered_backoff()
    )

    state = module.params["state"]
    method_names = {"list_resolver_rule_associations"}
    if state == "present":
        method_names.update(
            {
                "associate_resolver_rule",
                "disassociate_resolver_rule",
            }
        )
        if module.params["wait"]:
            method_names.add("get_resolver_rule_association")
    elif state == "absent":
        method_names.add("disassociate_resolver_rule")
        if module.params["wait"]:
            method_names.add("get_resolver_rule_association")
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
        "associate_resolver_rule": {"Name", "ResolverRuleId", "VPCId"},
        "disassociate_resolver_rule": {"ResolverRuleId", "VPCId"},
        "get_resolver_rule_association": {"ResolverRuleAssociationId"},
        "list_resolver_rule_associations": {"Filters", "MaxResults", "NextToken"},
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
