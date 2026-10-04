#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association
version_added: '1.9.0'
short_description: Manage AWS Systems Manager associations
description:
  - Parameter names in the returned association are preserved unchanged.
  - Manages AWS Systems Manager associations.
  - Manages the schedule expression, targets, and tags of an association
    keyed by its document name, or by O(association_name) when it is set.
  - Without O(association_name), any association of the document matches,
    including one created by another tool such as Quick Setup.
  - Updates preserve association fields not managed by this module, such as
    association parameters.
author:
  - Taylor Kimball (@tkimball83)
options:
  association_name:
    description:
      - The association name, which identifies one of several associations
        of the same document.
      - When set, only the association with this name is managed, and it is
        sent when the association is created.
      - This must be 3 to 128 letters, numbers, underscores, hyphens, or
        periods.
    type: str
  name:
    description:
      - The name of the SSM document association.
    required: true
    type: str
  schedule_expression:
    description:
      - The cron or rate expression that defines the association schedule.
      - This must be 1 to 256 characters.
      - When omitted, an existing association keeps its current schedule, and a
        new association runs once.
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
      - This must contain at most 5 targets.
      - When omitted, an existing association keeps its current targets, and a
        new association is created without targets.
    elements: dict
    suboptions:
      key:
        description:
          - The target key.
          - This must be 1 to 163 characters.
        required: true
        type: str
      values:
        description:
          - The target values.
          - This must contain at most 50 entries.
        elements: str
        required: true
        type: list
    type: list
notes:
  - O(tags) accepts at most 1000 entries; keys must contain 1 to 128 characters
    and values at most 256 characters.
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: The module reports the association that would result from the requested changes.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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

- name: Ensure a named SSM association is present
  linuxhq.aws.ssm_association:
    association_name: update-ssm-agent-weekly
    name: AWS-UpdateSSMAgent
    schedule_expression: rate(7 days)
    targets:
      - key: tag:Environment
        values:
          - production

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
  contains:
    association_id:
      description: Association identifier.
      returned: when available
      type: str
    association_name:
      description: Association name.
      returned: when configured
      type: str
    association_version:
      description: Association version.
      returned: when available
      type: str
    date:
      description: The date the association was created.
      returned: when available
      type: str
    document_version:
      description: The document version the association uses.
      returned: when available
      type: str
    last_execution_date:
      description: The date the association last ran.
      returned: when available
      type: str
    last_update_association_date:
      description: The date the association was last updated.
      returned: when available
      type: str
    name:
      description: SSM document name.
      returned: always
      type: str
    overview:
      description: The association status overview.
      returned: when available
      type: dict
    parameters:
      description:
        - The association parameters.
        - Parameter names keep their original case.
      returned: when configured
      type: dict
    schedule_expression:
      description: Association schedule expression.
      returned: when configured
      type: str
    tags:
      description: Association tags.
      returned: when O(tags) is supplied
      type: dict
    targets:
      description: Association targets.
      returned: when configured
      type: list
      elements: dict
      contains:
        key:
          description: Target key.
          returned: always
          type: str
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
import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_ssm_tags,
    require_valid_tags,
)

SSM_ASSOCIATION_RESOURCE_TYPE = "Association"
TARGET_DEFAULTS = {"values": []}


def comparable_targets(targets):
    normalized = []
    for target in targets or []:
        item = dict(TARGET_DEFAULTS, **target)

        if item.get("values"):
            item["values"] = sorted(set(item["values"]))

        normalized.append(item)

    unique = {json.dumps(item, sort_keys=True): item for item in normalized}
    return [unique[key] for key in sorted(unique)]


def association_description_from_response(module, response, message):
    if not isinstance(response, dict) or not isinstance(response.get("AssociationDescription"), dict):
        module.fail_json(msg=message)

    return response["AssociationDescription"]


def describe_association(client, module, association_id):
    try:
        response = client.describe_association(
            AssociationId=association_id,
            aws_retry=True,
        )
    except is_boto3_error_code("AssociationDoesNotExist"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to describe AWS Systems Manager association {association_id}",
        )

    return association_description_from_response(
        module,
        response,
        f"Unexpected response while describing AWS Systems Manager association {association_id}",
    )


def ensure_absent(client, module, current):
    name = module.params["name"]
    changed = current is not None
    association_id = (current or {}).get("AssociationId")

    if changed and not module.check_mode:
        try:
            client.delete_association(AssociationId=association_id, aws_retry=True)
        except is_boto3_error_code("AssociationDoesNotExist"):
            pass
        except (BotoCoreError, ClientError) as e:
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
    association_name = module.params.get("association_name")
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
    # Omitted options keep the association's current values, so only supplied options are compared and sent.
    desired_comparable = {}
    if schedule_expression is not None:
        desired_comparable["schedule_expression"] = schedule_expression

    if module.params["targets"] is not None:
        desired_comparable["targets"] = comparable_targets(module.params["targets"])

    current_comparable = None
    if normalized_current:
        current_comparable = {
            "schedule_expression": normalized_current.get("schedule_expression"),
            "targets": comparable_targets(normalized_current.get("targets")),
        }
        current_comparable = {key: value for key, value in current_comparable.items() if key in desired_comparable}

    aws_targets = desired_comparable.get("targets")
    association_id = (current or {}).get("AssociationId")
    desired = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "association_id": association_id,
                "association_name": association_name,
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
                response = client.create_association(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {
                                "association_name": association_name,
                                "name": name,
                                "schedule_expression": schedule_expression,
                                "tags": (ansible_dict_to_boto3_tag_list(tags) if tags else None),
                                "targets": aws_targets,
                            },
                            capitalize_first=True,
                        )
                    ),
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS Systems Manager association {name}",
                )

            association = association_description_from_response(
                module,
                response,
                f"AWS Systems Manager did not return the created association {name}",
            )
            if not association.get("AssociationId"):
                module.fail_json(msg=f"AWS Systems Manager did not return the created association {name}")

            if tags is not None:
                association["Tags"] = ansible_dict_to_boto3_tag_list(tags)

    else:
        changed = (current_comparable or {}) != desired_comparable
        resource_changed = changed
        if changed and not module.check_mode:
            update_request = {
                parameter: current.get(parameter)
                for parameter in get_boto3_client_method_parameters(client, "update_association")
            }
            update_request["AssociationId"] = association_id
            if schedule_expression is not None:
                update_request["ScheduleExpression"] = schedule_expression

            if aws_targets is not None:
                update_request["Targets"] = desired["Targets"]

            try:
                response = client.update_association(
                    **scrub_none_parameters(update_request),
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to update AWS Systems Manager association {name}",
                )

            association = association_description_from_response(
                module,
                response,
                f"AWS Systems Manager did not return the updated association {name}",
            )
            if not association.get("AssociationId"):
                module.fail_json(msg=f"AWS Systems Manager did not return the updated association {name}")

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
            if resource_changed and current is not None:
                association = association_with_tags(client, module, association)

            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(association.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )
            reconcile_ssm_tags(
                module,
                client,
                SSM_ASSOCIATION_RESOURCE_TYPE,
                association_id,
                tags_to_set,
                tag_keys_to_unset,
                "AWS Systems Manager association",
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
            ignore_list=["TargetMaps", "Parameters"],
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
        response = client.list_tags_for_resource(
            ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
            ResourceId=association_id,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Systems Manager {SSM_ASSOCIATION_RESOURCE_TYPE} {association_id}",
        )

    tags = response.get("TagList", []) if isinstance(response, dict) else None
    if not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags):
        module.fail_json(
            msg=f"Unexpected response while listing tags for AWS Systems Manager association {association_id}"
        )

    association["Tags"] = tags

    return association


def main():
    argument_spec = {
        "association_name": {"type": "str"},
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
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    state = module.params["state"]
    association_name = module.params["association_name"]
    name = module.params["name"]
    schedule_expression = module.params["schedule_expression"]
    targets = module.params["targets"]
    tags = module.params["tags"]

    if association_name is not None and not re.fullmatch(r"[a-zA-Z0-9_\-.]{3,128}", association_name):
        module.fail_json(msg="association_name must be 3 to 128 letters, numbers, underscores, hyphens, or periods")

    if state == "present":
        if schedule_expression is not None and not 1 <= len(schedule_expression) <= 256:
            module.fail_json(msg="schedule_expression must be 1 to 256 characters")

        if targets is not None and len(comparable_targets(targets)) > 5:
            module.fail_json(msg="targets must contain at most 5 targets")

        for target in targets or []:
            if not 1 <= len(target["key"]) <= 163:
                module.fail_json(msg="targets[].key must be 1 to 163 characters")

            if not target["values"]:
                module.fail_json(msg="targets[].values must contain at least one entry")

            if len(set(target["values"])) > 50:
                module.fail_json(msg="targets[].values must contain at most 50 entries")

        require_valid_tags(module, tags, 1000)

    client = module.client(
        "ssm",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["TooManyUpdates"]),
    )
    methods = {
        "list_associations": ("AssociationFilterList", "MaxResults", "NextToken"),
    }
    if state == "present":
        methods["describe_association"] = ("AssociationId",)
        methods["create_association"] = ("Name", "ScheduleExpression", "Targets")
        methods["update_association"] = (
            "AssociationId",
            "ScheduleExpression",
            "Targets",
        )
        if association_name is not None:
            methods["create_association"] += ("AssociationName",)

        if tags:
            methods["create_association"] += ("Tags",)

        if tags is not None:
            methods["list_tags_for_resource"] = ("ResourceId", "ResourceType")
            if tags:
                methods["add_tags_to_resource"] = (
                    "ResourceId",
                    "ResourceType",
                    "Tags",
                )

            if module.params["purge_tags"]:
                methods["remove_tags_from_resource"] = (
                    "ResourceId",
                    "ResourceType",
                    "TagKeys",
                )

    if state == "absent":
        methods["delete_association"] = ("AssociationId",)

    require_client_methods(module, client, "Systems Manager", methods)

    associations = query_list(
        module,
        client,
        "list_associations",
        "Associations",
        f"Unable to list AWS Systems Manager associations for {name}",
        AssociationFilterList=[{"key": "Name", "value": name}],
    )

    if any(not isinstance(association, dict) for association in associations):
        module.fail_json(msg=f"Unexpected response while listing AWS Systems Manager associations for {name}")

    matches = [
        association
        for association in associations
        if association.get("Name") == name
        and (association_name is None or association.get("AssociationName") == association_name)
    ]

    if any(
        not isinstance(association.get("AssociationId"), str) or not association["AssociationId"]
        for association in matches
    ):
        module.fail_json(msg=f"Unexpected response while listing AWS Systems Manager associations for {name}")

    if len(matches) > 1:
        association_ids = sorted(association["AssociationId"] for association in matches)
        module.fail_json(
            msg=(
                f"Multiple AWS Systems Manager associations exist for document {name}: "
                f"{', '.join(association_ids)}; set association_name to select one"
            )
        )

    current = matches[0] if matches else None

    if state == "present" and current is not None:
        current = describe_association(client, module, current["AssociationId"])

    if state == "present":
        ensure_present(client, module, current)

    if state == "absent":
        ensure_absent(client, module, current)


if __name__ == "__main__":
    main()
