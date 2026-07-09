#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association
short_description: Manage aws systems manager associations
description:
  - Manages AWS Systems Manager associations.
  - Manages the schedule expression, targets, and tags of an association
    keyed by its document name.
  - Updates replace the association definition; fields not managed by this
    module, such as association parameters, are removed by the AWS
    C(UpdateAssociation) API.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The name of the SSM document association.
    required: true
    type: str
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  schedule_expression:
    description:
      - The cron or rate expression that defines the association schedule.
      - This must be 1 to 256 characters.
      - This is required when O(state=present).
    type: str
  state:
    description:
      - Whether the association should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the association.
    type: dict
  targets:
    description:
      - The targets for the association.
      - This must contain at most 5 targets.
      - This is required when O(state=present).
    elements: dict
    suboptions:
      key:
        description:
          - The target key.
        required: true
        type: str
      values:
        description:
          - The target values.
        elements: str
        required: true
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
    tags:
      Name: update-ssm-agent
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

import json

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

SSM_ASSOCIATION_RESOURCE_TYPE = "Association"
TARGET_DEFAULTS = {"values": []}


def apply_tag_deltas(association, tags_to_set, tag_keys_to_unset):
    updated = dict(association)
    updated_tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        updated_tags.pop(tag_key, None)
    updated_tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(updated_tags)
    return updated


def comparable_targets(targets):
    normalized = []
    for target in targets or []:
        item = dict(TARGET_DEFAULTS, **target)

        if item.get("values"):
            item["values"] = sorted(item["values"])
        normalized.append(item)
    return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))


def ensure_absent(client, module, current):
    name = module.params["name"]
    changed = current is not None
    association_id = (current or {}).get("AssociationId")

    if changed and not module.check_mode:
        try:
            client.delete_association(AssociationId=association_id, aws_retry=True)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Systems Manager association {name}",
            )

    result = {
        "changed": changed,
        "name": name,
        "state": "absent",
    }

    if association_id:
        result["association_id"] = association_id

    module.exit_json(**result)


def ensure_present(client, module, current):
    name = module.params["name"]
    schedule_expression = module.params["schedule_expression"]
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    if tags is not None:
        current = association_with_tags(client, module, current)

    normalized_current = (
        boto3_resource_to_ansible_dict(
            current,
            ignore_list=["TargetMaps"],
            transform_tags=False,
            force_tags=False,
        )
        if current
        else None
    )
    current_comparable = None
    if normalized_current:
        current_comparable = {
            "schedule_expression": normalized_current.get("schedule_expression"),
            "targets": comparable_targets(normalized_current.get("targets")),
        }
    desired_comparable = {
        "schedule_expression": schedule_expression,
        "targets": comparable_targets(module.params["targets"]),
    }
    aws_targets = desired_comparable["targets"]
    association_id = (current or {}).get("AssociationId")
    desired = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "association_id": association_id,
                "name": name,
                "schedule_expression": schedule_expression,
                "targets": aws_targets,
            },
            capitalize_first=True,
        )
    )

    if current is None:
        changed = True
        resource_changed = True
        if module.check_mode:
            association = desired
            if tags is not None:
                association["Tags"] = ansible_dict_to_boto3_tag_list(tags)
        else:
            try:
                association = client.create_association(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {
                                "name": name,
                                "schedule_expression": schedule_expression,
                                "tags": (
                                    ansible_dict_to_boto3_tag_list(tags)
                                    if tags
                                    else None
                                ),
                                "targets": aws_targets,
                            },
                            capitalize_first=True,
                        )
                    ),
                    aws_retry=True,
                ).get("AssociationDescription", {})
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS Systems Manager association {name}",
                )

    else:
        changed = (current_comparable or {}) != desired_comparable
        resource_changed = changed
        if changed and not module.check_mode:
            try:
                association = client.update_association(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {
                                "association_id": association_id,
                                "schedule_expression": schedule_expression,
                                "targets": aws_targets,
                            },
                            capitalize_first=True,
                        )
                    ),
                    aws_retry=True,
                ).get("AssociationDescription", {})
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to update AWS Systems Manager association {name}",
                )

        elif changed and module.check_mode:
            association = dict(current)
            association.update(desired)
        else:
            association = current

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
            tags,
            purge_tags=purge_tags,
        )
    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        association_id = association.get("AssociationId")

        if association_id and tags is not None:
            if resource_changed:
                association = association_with_tags(client, module, association)
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(association.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )
            if tag_keys_to_unset:
                try:
                    client.remove_tags_from_resource(
                        ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
                        ResourceId=association_id,
                        TagKeys=tag_keys_to_unset,
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to remove tags from AWS Systems Manager "
                            f"association {association_id}"
                        ),
                    )

            if tags_to_set:
                try:
                    client.add_tags_to_resource(
                        ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
                        ResourceId=association_id,
                        Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to tag AWS Systems Manager association "
                            f"{association_id}"
                        ),
                    )

            association = apply_tag_deltas(association, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode and tags is not None:
        association = apply_tag_deltas(association, tags_to_set, tag_keys_to_unset)

    result = {
        "changed": changed,
        "name": name,
        "state": "present",
        "association": boto3_resource_to_ansible_dict(
            association,
            ignore_list=["TargetMaps"],
            transform_tags=True,
            force_tags=False,
        ),
    }

    association_id = association.get("AssociationId")

    if association_id:
        result["association_id"] = association_id

    module.exit_json(**result)


def association_with_tags(client, module, association):
    association_id = (association or {}).get("AssociationId")

    if not association_id:
        return association

    association = dict(association)

    try:
        association["Tags"] = client.list_tags_for_resource(
            ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
            ResourceId=association_id,
            aws_retry=True,
        ).get("TagList", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list tags for AWS Systems Manager "
                f"{SSM_ASSOCIATION_RESOURCE_TYPE} {association_id}"
            ),
        )

    return association


def main():
    argument_spec = {
        "name": {"required": True, "type": "str"},
        "purge_tags": {"default": True, "type": "bool"},
        "schedule_expression": {"type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "targets": {
            "elements": "dict",
            "options": {
                "key": {"no_log": False, "required": True, "type": "str"},
                "values": {"elements": "str", "required": True, "type": "list"},
            },
            "type": "list",
        },
        "tags": {"type": "dict"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[
            ("state", "present", ["schedule_expression", "targets"]),
        ],
        supports_check_mode=True,
    )
    state = module.params["state"]
    name = module.params["name"]
    tags = module.params["tags"]

    if state == "present":
        if not 1 <= len(module.params["schedule_expression"]) <= 256:
            module.fail_json(msg="schedule_expression must be 1 to 256 characters")

        if len(module.params["targets"]) > 5:
            module.fail_json(msg="targets must contain at most 5 targets")

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    method_names = {"list_associations"}
    if state == "present":
        method_names.update(
            {
                "create_association",
                "update_association",
            }
        )
        if tags is not None:
            method_names.add("list_tags_for_resource")
            if tags:
                method_names.add("add_tags_to_resource")
            if module.params["purge_tags"]:
                method_names.add("remove_tags_from_resource")
    elif state == "absent":
        method_names.add("delete_association")
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
                    "Installed botocore does not support Systems Manager "
                    f"{method_name}"
                )
            )

    required_method_parameters = {
        "add_tags_to_resource": {"ResourceId", "ResourceType", "Tags"},
        "create_association": {"Name", "ScheduleExpression", "Targets"},
        "delete_association": {"AssociationId"},
        "list_associations": {"AssociationFilterList", "MaxResults", "NextToken"},
        "list_tags_for_resource": {"ResourceId", "ResourceType"},
        "remove_tags_from_resource": {"ResourceId", "ResourceType", "TagKeys"},
        "update_association": {"AssociationId", "ScheduleExpression", "Targets"},
    }
    if tags:
        required_method_parameters["create_association"].add("Tags")

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Systems Manager "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    try:
        associations = paginated_query_with_retries(
            client,
            "list_associations",
            AssociationFilterList=[{"key": "Name", "value": name}],
        ).get("Associations", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list AWS Systems Manager associations for {name}",
        )

    matches = [
        association for association in associations if association.get("Name") == name
    ]

    if len(matches) > 1:
        association_ids = sorted(
            association.get("AssociationId", "") for association in matches
        )
        module.fail_json(
            msg=(
                "Multiple AWS Systems Manager associations exist for document "
                f"{name}: {', '.join(association_ids)}"
            )
        )

    current = matches[0] if matches else None

    if state == "present":
        ensure_present(client, module, current)
    elif state == "absent":
        ensure_absent(client, module, current)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
