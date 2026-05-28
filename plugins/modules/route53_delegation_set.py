#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: route53_delegation_set
short_description: Manage aws route53 delegation sets
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
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def ensure_absent(client, module):
    delegation_set = get_reusable_delegation_set(client, module)
    changed = delegation_set is not None
    delegation_set_id = (delegation_set or {}).get("Id")

    if changed and not module.check_mode:
        try:
            client.delete_reusable_delegation_set(
                Id=delegation_set_id,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to delete AWS Route53 reusable delegation set "
                    f"{module.params['name']}"
                ),
            )

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    delegation_set = get_reusable_delegation_set(client, module)
    desired_delegation_set = {"caller_reference": module.params["name"]}
    changed = delegation_set is None

    if changed and not module.check_mode:
        try:
            delegation_set = client.create_reusable_delegation_set(
                CallerReference=module.params["name"],
                aws_retry=True,
            ).get("DelegationSet")
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to create AWS Route53 reusable delegation set "
                    f"{module.params['name']}"
                ),
            )
        if delegation_set is None:
            delegation_set = get_reusable_delegation_set(client, module)
    elif changed and module.check_mode:
        delegation_set = desired_delegation_set

    result = {
        "changed": changed,
        "delegation_set": boto3_resource_to_ansible_dict(
            delegation_set, transform_tags=False, force_tags=False
        ),
        "name": module.params["name"],
        "state": "present",
    }
    delegation_set_id = (delegation_set or {}).get("Id")
    if delegation_set_id is not None:
        result["delegation_set_id"] = delegation_set_id

    module.exit_json(**result)


def list_reusable_delegation_sets(client, module):
    marker = None
    delegation_sets = []
    while True:
        request = {}
        if marker:
            request["Marker"] = marker
        try:
            response = client.list_reusable_delegation_sets(**request, aws_retry=True)
        except Exception as e:
            module.fail_json_aws(
                e, msg="Unable to list AWS Route53 reusable delegation sets"
            )
        delegation_sets.extend(response.get("DelegationSets", []))
        if not response.get("IsTruncated"):
            return delegation_sets
        marker = response.get("NextMarker")
        if not marker:
            module.fail_json(
                msg=(
                    "AWS Route53 reusable delegation sets response was "
                    "truncated without a NextMarker"
                )
            )


def get_reusable_delegation_set(client, module):
    name = module.params["name"]
    return next(
        (
            delegation_set
            for delegation_set in list_reusable_delegation_sets(client, module)
            if delegation_set.get("CallerReference") == name
        ),
        None,
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
    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
