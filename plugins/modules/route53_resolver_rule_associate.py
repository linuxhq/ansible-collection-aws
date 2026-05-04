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

import time
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.route53 import (
    list_resolver_rule_associations,
    normalize_resolver_rule_association,
)


def get_resolver_rule_association(client, module, resolver_rule_association_id):
    get_resolver_rule_association = AWSRetry.jittered_backoff()(
        client.get_resolver_rule_association
    )
    try:
        response = get_resolver_rule_association(
            ResolverRuleAssociationId=resolver_rule_association_id
        )
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule association {resolver_rule_association_id}",
        )
    return response.get("ResolverRuleAssociation")


def get_resolver_rule_association_by_rule_and_vpc(
    client, module, resolver_rule_id, vpc_id
):
    for association in list_resolver_rule_associations(client, module):
        if (
            association.get("ResolverRuleId") == resolver_rule_id
            and association.get("VPCId") == vpc_id
        ):
            return association
    return None


def wait_for_resolver_rule_association_status(
    client, module, resolver_rule_association_id, statuses, name
):
    deadline = time.time() + module.params["wait_timeout"]

    while time.time() < deadline:
        association = get_resolver_rule_association(
            client, module, resolver_rule_association_id
        )
        if association is None and "deleted" in statuses:
            return None
        if (
            association is not None
            and association.get("Status", "").lower() in statuses
        ):
            return association
        time.sleep(module.params["wait_delay"])

    module.fail_json(
        msg=f"Timed out waiting for AWS Route53 Resolver rule association {name}",
        resolver_rule_association_id=resolver_rule_association_id,
    )


def ensure_present(client, module):
    association = get_resolver_rule_association_by_rule_and_vpc(
        client, module, module.params["resolver_rule_id"], module.params["vpc_id"]
    )
    changed = association is None

    if changed and not module.check_mode:
        associate_resolver_rule = AWSRetry.jittered_backoff()(
            client.associate_resolver_rule
        )
        try:
            response = associate_resolver_rule(
                Name=module.params["name"],
                ResolverRuleId=module.params["resolver_rule_id"],
                VPCId=module.params["vpc_id"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 Resolver rule association {module.params['name']}",
            )
        association = response.get("ResolverRuleAssociation")
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
        "resolver_rule_association": normalize_resolver_rule_association(association),
        "state": "present",
    }
    if association is not None and association.get("Id") is not None:
        result["resolver_rule_association_id"] = association["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    association = get_resolver_rule_association_by_rule_and_vpc(
        client, module, module.params["resolver_rule_id"], module.params["vpc_id"]
    )
    changed = association is not None

    if changed and not module.check_mode:
        resolver_rule_association_id = association["Id"]
        disassociate_resolver_rule = AWSRetry.jittered_backoff()(
            client.disassociate_resolver_rule
        )
        try:
            disassociate_resolver_rule(
                ResolverRuleId=module.params["resolver_rule_id"],
                VPCId=module.params["vpc_id"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 Resolver rule association {module.params['name']}",
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
