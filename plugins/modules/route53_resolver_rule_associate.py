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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in (
        "ResourceNotFoundException",
    )


def list_resolver_rule_associations(client, module):
    associations = []
    next_token = None

    while True:
        kwargs = {}
        if next_token:
            kwargs["NextToken"] = next_token

        try:
            response = client.list_resolver_rule_associations(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Route53 Resolver rule associations",
            )

        associations.extend(response.get("ResolverRuleAssociations", []))
        next_token = response.get("NextToken")
        if not next_token:
            break

    return associations


def get_resolver_rule_association(client, module, resolver_rule_association_id):
    try:
        response = client.get_resolver_rule_association(
            ResolverRuleAssociationId=resolver_rule_association_id
        )
    except Exception as e:
        if is_not_found_error(e):
            return None
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Route53 Resolver rule association {resolver_rule_association_id}",
        )
    return response.get("ResolverRuleAssociation")


def get_resolver_rule_association_by_rule_and_vpc(client, module):
    for association in list_resolver_rule_associations(client, module):
        if (
            association.get("ResolverRuleId") == module.params["resolver_rule_id"]
            and association.get("VPCId") == module.params["vpc_id"]
        ):
            return association
    return None


def wait_for_status(client, module, resolver_rule_association_id, statuses):
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
        msg=f"Timed out waiting for AWS Route53 Resolver rule association {module.params['name']}",
        resolver_rule_association_id=resolver_rule_association_id,
    )


def normalize(association):
    if association is None:
        return None
    return camel_dict_to_snake_dict(association)


def ensure_present(client, module):
    association = get_resolver_rule_association_by_rule_and_vpc(client, module)
    changed = association is None

    if changed and not module.check_mode:
        try:
            response = client.associate_resolver_rule(
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
            association = wait_for_status(
                client, module, association["Id"], {"complete"}
            )
    elif changed and module.check_mode:
        association = {"Name": module.params["name"]}

    result = {
        "changed": changed,
        "name": module.params["name"],
        "resolver_rule_association": normalize(association),
        "state": "present",
    }
    if association is not None and association.get("Id") is not None:
        result["resolver_rule_association_id"] = association["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    association = get_resolver_rule_association_by_rule_and_vpc(client, module)
    changed = association is not None

    if changed and not module.check_mode:
        resolver_rule_association_id = association["Id"]
        try:
            client.disassociate_resolver_rule(
                ResolverRuleId=module.params["resolver_rule_id"],
                VPCId=module.params["vpc_id"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 Resolver rule association {module.params['name']}",
            )
        if module.params["wait"]:
            wait_for_status(client, module, resolver_rule_association_id, {"deleted"})

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
