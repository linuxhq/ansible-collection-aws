#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association
version_added: "1.9.5"
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
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
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
  tags:
    description:
      - Tags to apply to the association.
    type: dict
  targets:
    description:
      - The targets for the association.
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

from ansible.module_utils.common.dict_transformations import (
    recursive_diff,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
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


def ensure_absent(client, module, current):
    changed = current is not None
    association_id = (current or {}).get("AssociationId")

    if changed and not module.check_mode:
        try:
            client.delete_association(AssociationId=association_id, aws_retry=True)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to delete AWS Systems Manager association "
                    f"{module.params['name']}"
                ),
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
    current = association_with_tags(client, module, current)
    desired_parameters = {
        "schedule_expression": module.params["schedule_expression"],
        "targets": module.params["targets"],
    }
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
            "targets": [
                dict(TARGET_DEFAULTS, **target)
                for target in normalized_current.get("targets", [])
            ],
        }
    desired_comparable = {
        "schedule_expression": desired_parameters["schedule_expression"],
        "targets": [
            dict(TARGET_DEFAULTS, **target)
            for target in desired_parameters.get("targets", [])
        ],
    }
    aws_targets = desired_comparable["targets"]
    association_id = (current or {}).get("AssociationId")
    desired = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "association_id": association_id,
                "name": module.params["name"],
                "schedule_expression": module.params["schedule_expression"],
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
            if module.params["tags"] is not None:
                association["Tags"] = ansible_dict_to_boto3_tag_list(
                    module.params["tags"]
                )
        else:
            try:
                association = client.create_association(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {
                                "name": module.params["name"],
                                "schedule_expression": module.params[
                                    "schedule_expression"
                                ],
                                "tags": (
                                    ansible_dict_to_boto3_tag_list(
                                        module.params["tags"]
                                    )
                                    if module.params["tags"] is not None
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
                    msg=(
                        "Unable to create AWS Systems Manager association "
                        f"{module.params['name']}"
                    ),
                )
    else:
        changed = (
            recursive_diff((current_comparable) or {}, (desired_comparable) or {})
            is not None
        )
        resource_changed = changed
        if changed and not module.check_mode:
            try:
                association = client.update_association(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {
                                "association_id": association_id,
                                "schedule_expression": module.params[
                                    "schedule_expression"
                                ],
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
                    msg=(
                        "Unable to update AWS Systems Manager association "
                        f"{module.params['name']}"
                    ),
                )
        elif changed and module.check_mode:
            association = desired
        else:
            association = current

    tags_to_set, tag_keys_to_unset = tag_changes(module, current)
    changed = bool(changed or tags_to_set or tag_keys_to_unset)
    if changed and not module.check_mode:
        association_id = association.get("AssociationId")
        if association_id and module.params["tags"] is not None:
            tags_to_set, tag_keys_to_unset = tag_changes(
                module,
                association_with_tags(client, module, association),
            )
            apply_tag_changes(
                client,
                module,
                association_id,
                tags_to_set,
                tag_keys_to_unset,
            )
            association = association_with_tags(client, module, association)
    elif changed and module.check_mode and module.params["tags"] is not None:
        association["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])

    result = {
        "changed": changed,
        "name": module.params["name"],
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
    association["Tags"] = get_resource_tags(
        client,
        module,
        SSM_ASSOCIATION_RESOURCE_TYPE,
        association_id,
    )
    return association


def get_resource_tags(client, module, resource_type, resource_id):
    try:
        return client.list_tags_for_resource(
            ResourceType=resource_type,
            ResourceId=resource_id,
            aws_retry=True,
        ).get("TagList", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Systems Manager {resource_type} {resource_id}",
        )


def tag_changes(module, current):
    if module.params["tags"] is None:
        return {}, []
    current_tags = boto3_tag_list_to_ansible_dict((current or {}).get("Tags", []))
    return compare_aws_tags(
        current_tags,
        module.params["tags"],
        purge_tags=module.params["purge_tags"],
    )


def apply_tag_changes(client, module, resource_id, tags_to_set, tag_keys_to_unset):
    if tag_keys_to_unset:
        try:
            client.remove_tags_from_resource(
                ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
                ResourceId=resource_id,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from AWS Systems Manager association {resource_id}",
            )

    if tags_to_set:
        try:
            client.add_tags_to_resource(
                ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
                ResourceId=resource_id,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag AWS Systems Manager association {resource_id}",
            )


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
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    current = next(
        (
            association
            for association in paginated_query_with_retries(
                client,
                "list_associations",
                AssociationFilterList=[{"key": "Name", "value": module.params["name"]}],
            ).get("Associations", [])
            if association.get("Name") == module.params["name"]
        ),
        None,
    )

    if module.params["state"] == "present":
        ensure_present(client, module, current)
    ensure_absent(client, module, current)


if __name__ == "__main__":
    main()
