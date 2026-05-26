#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document
short_description: Manage aws systems manager documents
description:
  - Manages AWS Systems Manager documents.
  - Supports creating, updating, and deleting JSON documents.
  - Accepts structured Ansible YAML content and serializes it to JSON for AWS.
  - Converts document content input keys to AWS format for comparison and API requests.
  - O(document_type) is immutable after creation.
author:
  - Taylor Kimball (@tkimball83)
options:
  content:
    description:
      - The document content to manage.
      - Provide the content as structured Ansible YAML data.
      - The module serializes the content to JSON for AWS Systems Manager.
      - Content keys may be provided in snake_case or AWS native camelCase.
      - Required when O(state=present).
    type: dict
  document_type:
    description:
      - The Systems Manager document type to create.
      - Required when O(state=present).
    type: str
  document_version:
    description:
      - The document version to read and update.
    default: $LATEST
    type: str
  name:
    description:
      - The Systems Manager document name.
    required: true
    type: str
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  state:
    description:
      - Whether the document should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the Systems Manager document.
    type: dict
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure a Session Manager document is present
  linuxhq.aws.ssm_document:
    content:
      schema_version: "1.0"
      description: Document to hold regional settings for Session Manager
      session_type: Standard_Stream
      inputs:
        idle_session_timeout: 60
    document_type: Session
    name: SSM-SessionManagerRunShell
    tags:
      Name: SSM-SessionManagerRunShell

- name: Ensure a Session Manager document is absent
  linuxhq.aws.ssm_document:
    name: SSM-SessionManagerRunShell
    state: absent
"""

RETURN = r"""
document:
  description:
    - The current AWS Systems Manager document after module execution.
  returned: when state is present
  type: dict
name:
  description: The managed Systems Manager document name.
  returned: always
  type: str
state:
  description: The requested state of the document.
  returned: always
  type: str
"""

import json

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
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
)

SSM_DOCUMENT_RESOURCE_TYPE = "Document"


def ensure_absent(client, module):
    current = get_document(client, module)
    changed = current is not None

    if changed and not module.check_mode:
        try:
            client.delete_document(
                Name=module.params["name"],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to delete AWS Systems Manager document "
                    f"{module.params['name']}"
                ),
            )

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def ensure_present(client, module):
    current = get_document(client, module)
    desired = {
        "content": module.params["content"],
        "document_type": module.params["document_type"],
        "name": module.params["name"],
    }
    current_document = (
        {
            "content": snake_dict_to_camel_dict(
                document_content(current), capitalize_first=False
            ),
            "document_type": current.get("DocumentType"),
        }
        if current is not None
        else None
    )
    desired_comparable = {
        "content": snake_dict_to_camel_dict(desired["content"], capitalize_first=False),
        "document_type": desired["document_type"],
    }
    current_comparable = current_document
    desired.update(desired_comparable)

    if current is None:
        changed = True
        resource_changed = True
    else:
        if current_comparable["document_type"] != desired_comparable["document_type"]:
            module.fail_json(
                msg=(
                    "Unable to update AWS Systems Manager document "
                    f"{module.params['name']}: immutable fields differ"
                )
            )
        changed = current_comparable != desired_comparable
        resource_changed = changed

    tags_to_set, tag_keys_to_unset = ({}, [])
    if module.params["tags"] is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
            module.params["tags"],
            purge_tags=module.params["purge_tags"],
        )
    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if resource_changed:
            desired_content = json.dumps(
                desired["content"],
                separators=(",", ":"),
                sort_keys=True,
            )

        if current is None:
            try:
                request = {
                    "Content": desired_content,
                    "DocumentFormat": "JSON",
                    "DocumentType": desired["document_type"],
                    "Name": desired["name"],
                }
                if module.params["tags"] is not None:
                    request["Tags"] = ansible_dict_to_boto3_tag_list(
                        module.params["tags"]
                    )
                client.create_document(**request, aws_retry=True)
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to manage AWS Systems Manager document "
                        f"{module.params['name']}"
                    ),
                )
        elif resource_changed:
            try:
                client.update_document(
                    Content=desired_content,
                    DocumentFormat="JSON",
                    DocumentVersion=module.params["document_version"],
                    Name=desired["name"],
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to manage AWS Systems Manager document "
                        f"{module.params['name']}"
                    ),
                )
        if current is None or resource_changed:
            current = get_document(client, module)
        if current is not None and module.params["tags"] is not None:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
                module.params["tags"],
                purge_tags=module.params["purge_tags"],
            )
            apply_tag_changes(
                client,
                module,
                module.params["name"],
                tags_to_set,
                tag_keys_to_unset,
            )
            current = document_with_updated_tags(
                current, tags_to_set, tag_keys_to_unset
            )
    elif changed and module.check_mode:
        current = desired
        if module.params["tags"] is not None:
            current["tags"] = module.params["tags"]

    document = current
    if (current or {}).get("Name") is not None:
        document = normalize_document(current, force_content=True)
    result = {
        "changed": changed,
        "document": document,
        "name": module.params["name"],
        "state": "present",
    }

    module.exit_json(**result)


def get_document(client, module):
    try:
        document = client.get_document(
            DocumentFormat="JSON",
            DocumentVersion=module.params["document_version"],
            Name=module.params["name"],
            aws_retry=True,
        )
    except is_boto3_error_code(("InvalidDocument", "InvalidDocumentOperation")):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Systems Manager document {module.params['name']}",
        )
    document["Tags"] = get_resource_tags(
        client,
        module,
        SSM_DOCUMENT_RESOURCE_TYPE,
        module.params["name"],
    )
    return document


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


def document_with_updated_tags(document, tags_to_set, tag_keys_to_unset):
    document = dict(document)
    tags = boto3_tag_list_to_ansible_dict(document.get("Tags", []))
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)
    tags.update(tags_to_set)
    document["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return document


def apply_tag_changes(client, module, resource_id, tags_to_set, tag_keys_to_unset):
    if tag_keys_to_unset:
        try:
            client.remove_tags_from_resource(
                ResourceType=SSM_DOCUMENT_RESOURCE_TYPE,
                ResourceId=resource_id,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from AWS Systems Manager document {resource_id}",
            )

    if tags_to_set:
        try:
            client.add_tags_to_resource(
                ResourceType=SSM_DOCUMENT_RESOURCE_TYPE,
                ResourceId=resource_id,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag AWS Systems Manager document {resource_id}",
            )


def document_content(document, strict=True):
    if not document or document.get("Content") is None:
        return {}
    content = document.get("Content")
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except ValueError:
        if strict:
            raise
        return content


def normalize_document(document, strict_content=True, force_content=False):
    if not document:
        return document

    content = document_content(document, strict_content)
    normalized = boto3_resource_to_ansible_dict(
        dict(document, Content=content),
        transform_tags=True,
        force_tags=False,
    )
    if force_content and "content" not in normalized:
        normalized["content"] = {}
    return normalized


def main():
    argument_spec = {
        "content": {"type": "dict"},
        "document_type": {"type": "str"},
        "document_version": {"default": "$LATEST", "type": "str"},
        "name": {"required": True, "type": "str"},
        "purge_tags": {"default": True, "type": "bool"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"type": "dict"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["content", "document_type"])],
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
