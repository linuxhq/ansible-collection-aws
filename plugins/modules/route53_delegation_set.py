#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set
version_added: 1.9.1
short_description: Manage AWS Route53 reusable delegation sets
description:
  - Manages AWS Route53 reusable delegation sets.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The delegation set caller reference.
    required: true
    type: str
  state:
    description:
      - Whether the delegation set should exist.
    choices:
      - absent
      - present
    default: present
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a Route53 reusable delegation set is present
  linuxhq.aws.route53_delegation_set:
    name: molecule-01

- name: Ensure a Route53 reusable delegation set is absent
  linuxhq.aws.route53_delegation_set:
    name: molecule-01
    state: absent
"""

RETURN = r"""
delegation_set:
  description:
    - The current reusable delegation set after module execution.
  returned: when state is present
  type: dict
delegation_set_id:
  description:
    - The reusable delegation set ID.
  returned: when a delegation set exists after module execution
  type: str
name:
  description:
    - The requested delegation set caller reference.
  returned: always
  type: str
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.route53 import (
    list_delegation_sets,
    normalize_delegation_set,
)


def get_delegation_set_by_name(client, module, name):
    for delegation_set in list_delegation_sets(client, module):
        if delegation_set.get("CallerReference") == name:
            return delegation_set
    return None


def ensure_present(client, module):
    delegation_set = get_delegation_set_by_name(client, module, module.params["name"])
    changed = delegation_set is None

    if changed and not module.check_mode:
        create_reusable_delegation_set = AWSRetry.jittered_backoff()(
            client.create_reusable_delegation_set
        )
        try:
            response = create_reusable_delegation_set(
                CallerReference=module.params["name"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 reusable delegation set {module.params['name']}",
            )
        delegation_set = response.get("DelegationSet") or get_delegation_set_by_name(
            client, module, module.params["name"]
        )
    elif changed and module.check_mode:
        delegation_set = {
            "CallerReference": module.params["name"],
        }

    result = {
        "changed": changed,
        "delegation_set": normalize_delegation_set(delegation_set),
        "name": module.params["name"],
        "state": "present",
    }
    if delegation_set is not None and delegation_set.get("Id") is not None:
        result["delegation_set_id"] = delegation_set["Id"]

    module.exit_json(**result)


def ensure_absent(client, module):
    delegation_set = get_delegation_set_by_name(client, module, module.params["name"])
    changed = delegation_set is not None

    if changed and not module.check_mode:
        delete_reusable_delegation_set = AWSRetry.jittered_backoff()(
            client.delete_reusable_delegation_set
        )
        try:
            delete_reusable_delegation_set(
                Id=delegation_set["Id"],
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 reusable delegation set {module.params['name']}",
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
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    client = module.client("route53")

    if module.params["state"] == "present":
        ensure_present(client, module)

    ensure_absent(client, module)


if __name__ == "__main__":
    main()
