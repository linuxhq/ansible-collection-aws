#!/usr/bin/python
# Copyright: Ansible Project
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
      - This must be 1 to 128 characters.
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
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def ensure_absent(client, module):
    name = module.params["name"]
    delegation_set = get_reusable_delegation_set(client, module)
    changed = delegation_set is not None
    delegation_set_id = (delegation_set or {}).get("Id")

    if changed and not module.check_mode:
        try:
            client.delete_reusable_delegation_set(
                Id=delegation_set_id,
                aws_retry=True,
            )
        except is_boto3_error_code("NoSuchDelegationSet"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Route53 reusable delegation set {name}",
            )

    module.exit_json(
        changed=changed,
        name=name,
        state="absent",
    )


def ensure_present(client, module):
    name = module.params["name"]
    delegation_set = get_reusable_delegation_set(client, module)
    changed = delegation_set is None

    if changed and not module.check_mode:
        try:
            response = client.create_reusable_delegation_set(
                CallerReference=name,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Route53 reusable delegation set {name}",
            )

        delegation_set = response.get("DelegationSet") if isinstance(response, dict) else None
        if (
            not isinstance(delegation_set, dict)
            or delegation_set.get("CallerReference") != name
            or not isinstance(delegation_set.get("Id"), str)
        ):
            delegation_set = get_reusable_delegation_set(client, module)
        if delegation_set is None:
            module.fail_json(msg=("AWS Route53 did not return the created reusable delegation set " f"{name}"))
    elif changed and module.check_mode:
        delegation_set = {"CallerReference": name}

    result = {
        "changed": changed,
        "delegation_set": boto3_resource_to_ansible_dict(delegation_set, transform_tags=False, force_tags=False),
        "name": name,
        "state": "present",
    }
    delegation_set_id = (delegation_set or {}).get("Id")

    if delegation_set_id is not None:
        result["delegation_set_id"] = delegation_set_id

    module.exit_json(**result)


def get_reusable_delegation_set(client, module):
    name = module.params["name"]
    delegation_sets = query_list(
        module,
        client,
        "list_reusable_delegation_sets",
        "DelegationSets",
        "Unable to list AWS Route53 reusable delegation sets",
    )
    for delegation_set in delegation_sets:
        if not isinstance(delegation_set, dict) or not isinstance(delegation_set.get("CallerReference"), str):
            module.fail_json(
                msg="Unable to list AWS Route53 reusable delegation sets: AWS returned an invalid response"
            )
        if delegation_set["CallerReference"] != name:
            continue
        if not isinstance(delegation_set.get("Id"), str):
            module.fail_json(
                msg="Unable to list AWS Route53 reusable delegation sets: AWS returned an invalid response"
            )
        return delegation_set

    return None


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
    state = module.params["state"]

    if not 1 <= len(module.params["name"]) <= 128:
        module.fail_json(msg="name must be 1 to 128 characters")

    client = module.client("route53", retry_decorator=AWSRetry.jittered_backoff())
    methods = {"list_reusable_delegation_sets": ("Marker", "MaxItems")}
    if state == "present":
        methods["create_reusable_delegation_set"] = ("CallerReference",)
    if state == "absent":
        methods["delete_reusable_delegation_set"] = ("Id",)

    require_client_methods(module, client, "Route53", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
