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
      - Key: InstanceIds
        Values:
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
proposed_association:
  description:
    - The association values that would exist after the requested change.
  returned: when changed and state is present
  type: dict
state:
  description: The requested state of the association.
  returned: always
  type: str
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def normalize_association(association):
    normalized = camel_dict_to_snake_dict(association)
    for key, target in (
        ("Targets", "targets"),
        ("TargetMaps", "target_maps"),
    ):
        if key in association:
            normalized[target] = association[key]
    return normalized


def canonicalize_targets(targets):
    normalized = []
    for target in targets or []:
        normalized.append(
            {
                "Key": target["Key"],
                "Values": sorted(target.get("Values", [])),
            }
        )
    return sorted(normalized, key=lambda item: item["Key"])


def list_associations(client, module):
    associations = []
    next_token = None

    try:
        while True:
            request = {}
            if next_token:
                request["NextToken"] = next_token
            response = client.list_associations(**request)
            associations.extend(response.get("Associations", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Systems Manager associations")

    return associations


def find_association(associations, name):
    for association in associations:
        if association.get("Name") == name:
            return association
    return None


def build_desired_association(module, association_id=None):
    desired = {
        "Name": module.params["name"],
        "ScheduleExpression": module.params["schedule_expression"],
        "Targets": module.params["targets"],
    }
    if association_id is not None:
        desired["AssociationId"] = association_id
    return desired


def ensure_present(client, module, current):
    desired_targets = canonicalize_targets(module.params["targets"])

    if current is None:
        changed = True
        proposed = build_desired_association(module)
        if module.check_mode:
            association = proposed
        else:
            try:
                response = client.create_association(
                    Name=module.params["name"],
                    ScheduleExpression=module.params["schedule_expression"],
                    Targets=module.params["targets"],
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
        proposed = build_desired_association(module, current.get("AssociationId"))
        if changed and not module.check_mode:
            try:
                response = client.update_association(
                    AssociationId=current["AssociationId"],
                    ScheduleExpression=module.params["schedule_expression"],
                    Targets=module.params["targets"],
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to update AWS Systems Manager association {module.params['name']}",
                )
            association = response.get("AssociationDescription", {})
        elif changed and module.check_mode:
            association = proposed
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
    if changed:
        result["proposed_association"] = normalize_association(proposed)
    module.exit_json(**result)


def ensure_absent(client, module, current):
    changed = current is not None

    if changed and not module.check_mode:
        try:
            client.delete_association(AssociationId=current["AssociationId"])
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
        "targets": {"elements": "dict", "type": "list"},
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
