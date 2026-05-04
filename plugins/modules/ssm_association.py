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
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    list_associations,
    normalize_association,
)


def aws_target(target):
    return scrub_none_parameters(
        {
            "Key": target.get("key"),
            "Values": target.get("values") or [],
        }
    )


def aws_targets(targets):
    return [aws_target(target) for target in targets or []]


def canonicalize_targets(targets):
    normalized = []
    for target in targets or []:
        key = target.get("key", target.get("Key"))
        values = target.get("values", target.get("Values", [])) or []
        normalized.append(
            {
                "Key": key,
                "Values": sorted(values),
            }
        )
    return sorted(normalized, key=lambda item: item["Key"] or "")


def build_desired_association(module, association_id=None):
    desired = {
        "Name": module.params["name"],
        "ScheduleExpression": module.params["schedule_expression"],
        "Targets": aws_targets(module.params["targets"]),
    }
    if association_id is not None:
        desired["AssociationId"] = association_id
    return desired


def find_association(associations, name):
    for association in associations:
        if association.get("Name") == name:
            return association
    return None


def ensure_present(client, module, current):
    desired_targets = canonicalize_targets(module.params["targets"])

    if current is None:
        changed = True
        desired = build_desired_association(module)
        if module.check_mode:
            association = desired
        else:
            create_association = AWSRetry.jittered_backoff()(client.create_association)
            try:
                response = create_association(
                    Name=module.params["name"],
                    ScheduleExpression=module.params["schedule_expression"],
                    Targets=aws_targets(module.params["targets"]),
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS Systems Manager association {module.params['name']}",
                )
            association = response.get("AssociationDescription", {})
    else:
        changed = (
            current.get("ScheduleExpression") != module.params["schedule_expression"]
            or canonicalize_targets(current.get("Targets", [])) != desired_targets
        )
        desired = build_desired_association(module, current.get("AssociationId"))
        if changed and not module.check_mode:
            update_association = AWSRetry.jittered_backoff()(client.update_association)
            try:
                response = update_association(
                    AssociationId=current["AssociationId"],
                    ScheduleExpression=module.params["schedule_expression"],
                    Targets=aws_targets(module.params["targets"]),
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to update AWS Systems Manager association {module.params['name']}",
                )
            association = response.get("AssociationDescription", {})
        elif changed and module.check_mode:
            association = desired
        else:
            association = current

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "present",
        "association": normalize_association(association),
    }
    association_id = association.get("AssociationId")
    if association_id:
        result["association_id"] = association_id
    module.exit_json(**result)


def ensure_absent(client, module, current):
    changed = current is not None

    if changed and not module.check_mode:
        delete_association = AWSRetry.jittered_backoff()(client.delete_association)
        try:
            delete_association(AssociationId=current["AssociationId"])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Systems Manager association {module.params['name']}",
            )

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "absent",
    }
    if current and current.get("AssociationId"):
        result["association_id"] = current["AssociationId"]
    module.exit_json(**result)


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

    current = find_association(list_associations(client, module), module.params["name"])

    if module.params["state"] == "present":
        ensure_present(client, module, current)
    ensure_absent(client, module, current)


if __name__ == "__main__":
    main()
