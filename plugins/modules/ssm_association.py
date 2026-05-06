#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association
version_added: 1.9.1
short_description: Manage AWS Systems Manager associations
description:
  - Manages AWS Systems Manager associations.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The name of the SSM document association.
    required: true
    type: str
  schedule_expression:
    description:
      - The cron or rate expression that defines the association schedule.
    type: str
  state:
    description:
      - Whether the association should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  targets:
    description:
      - The targets for the association.
    elements: dict
    suboptions:
      key:
        description:
          - The target key.
        type: str
      values:
        description:
          - The target values.
        elements: str
        type: list
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure an SSM association is present
  linuxhq.aws.ssm_association:
    name: AWS-UpdateSSMAgent
    schedule_expression: cron(0 0 * * ? *)
    targets:
      - key: InstanceIds
        values:
          - "*"

- name: Ensure an SSM association is absent
  linuxhq.aws.ssm_association:
    name: AWS-UpdateSSMAgent
    state: absent
"""

RETURN = r"""
association:
  description:
    - The current AWS Systems Manager association after module execution.
  returned: when state is present
  type: dict
association_id:
  description: The AWS Systems Manager association identifier.
  returned: when an association exists
  type: str
name:
  description: The managed association name.
  returned: always
  type: str
state:
  description: The requested state of the association.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.fields import (
    aws_field_values,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    canonicalize_list,
    field_differences,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    aws_ssm_targets,
    get_ssm_association_by_name,
    normalize_ssm_association,
)

COMPARE_ITEMS = ["schedule_expression", "targets"]


def build_desired_association(module, targets, association_id=None):
    desired = {
        "Name": module.params["name"],
        "ScheduleExpression": module.params["schedule_expression"],
        "Targets": targets,
    }
    if association_id is not None:
        desired["AssociationId"] = association_id
    return desired


def canonical_target(target):
    values = aws_field_values(target, ("key", "values"))
    return {
        "Key": values.get("key"),
        "Values": sorted(values.get("values") or []),
    }


def canonicalize_targets(targets):
    return canonicalize_list(targets, canonical_target, target_sort_key)


def comparable_association(association):
    if association is None:
        return None
    values = aws_field_values(association, ("schedule_expression", "targets"))
    return {
        "schedule_expression": values.get("schedule_expression"),
        "targets": canonicalize_targets(values.get("targets") or []),
    }


def ensure_absent(client, module, current):
    changed = current is not None
    association_id = current.get("AssociationId") if current is not None else None

    if changed and not module.check_mode:
        aws_response(
            client,
            module,
            "delete_association",
            error_message=(
                "Unable to delete AWS Systems Manager association "
                f"{module.params['name']}"
            ),
            AssociationId=association_id,
        )

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "absent",
    }
    if association_id:
        result["association_id"] = association_id
    module.exit_json(**result)


def ensure_present(client, module, current):
    aws_targets = aws_ssm_targets(module.params["targets"], default_values=True)
    desired_targets = canonicalize_targets(aws_targets)

    if current is None:
        changed = True
        desired = build_desired_association(module, aws_targets)
        if module.check_mode:
            association = desired
        else:
            association = aws_resource(
                client,
                module,
                "create_association",
                "AssociationDescription",
                default={},
                error_message=(
                    "Unable to create AWS Systems Manager association "
                    f"{module.params['name']}"
                ),
                Name=module.params["name"],
                ScheduleExpression=module.params["schedule_expression"],
                Targets=aws_targets,
            )
    else:
        _, changed = field_differences(
            comparable_association(current),
            {
                "schedule_expression": module.params["schedule_expression"],
                "targets": desired_targets,
            },
            COMPARE_ITEMS,
        )
        association_id = current.get("AssociationId")
        desired = build_desired_association(
            module,
            aws_targets,
            association_id,
        )
        if changed and not module.check_mode:
            association = aws_resource(
                client,
                module,
                "update_association",
                "AssociationDescription",
                default={},
                error_message=(
                    "Unable to update AWS Systems Manager association "
                    f"{module.params['name']}"
                ),
                AssociationId=association_id,
                ScheduleExpression=module.params["schedule_expression"],
                Targets=aws_targets,
            )
        elif changed and module.check_mode:
            association = desired
        else:
            association = current

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "present",
        "association": normalize_ssm_association(association),
    }
    association_id = association.get("AssociationId")
    if association_id:
        result["association_id"] = association_id
    module.exit_json(**result)


def target_sort_key(target):
    return target["Key"] or ""


def main():
    argument_spec = {
        "name": {"required": True, "type": "str"},
        "schedule_expression": {"type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "targets": {
            "elements": "dict",
            "options": {
                "key": {"type": "str"},
                "values": {"elements": "str", "type": "list"},
            },
            "type": "list",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[
            ("state", "present", ["schedule_expression", "targets"]),
        ],
        supports_check_mode=True,
    )
    client = module.client("ssm")

    current = get_ssm_association_by_name(client, module, module.params["name"])

    if module.params["state"] == "present":
        ensure_present(client, module, current)
    ensure_absent(client, module, current)


if __name__ == "__main__":
    main()
