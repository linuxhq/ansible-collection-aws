#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document
version_added: 1.9.1
short_description: Manage AWS Systems Manager documents
description:
  - Manages AWS Systems Manager documents.
  - Supports creating, updating, and deleting JSON documents.
  - Accepts structured Ansible YAML content and serializes it to JSON for AWS.
  - Normalizes document content keys to snake_case for comparison and return values.
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
  state:
    description:
      - Whether the document should exist.
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
    camel_dict_to_snake_dict,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    get_document as get_ssm_document,
)


def build_desired_document(module):
    return {
        "content": camel_dict_to_snake_dict(module.params["content"]),
        "document_type": module.params["document_type"],
        "name": module.params["name"],
    }


def get_document(client, module):
    return get_ssm_document(
        client,
        module,
        module.params["name"],
        document_version=module.params["document_version"],
        default_content={},
        include_missing_content=True,
    )


def ensure_present(client, module):
    current = get_document(client, module)
    desired = build_desired_document(module)
    changed = current is None or current.get("content") != desired["content"]

    if changed and not module.check_mode:
        content = snake_dict_to_camel_dict(desired["content"])
        try:
            if current is None:
                create_document = AWSRetry.jittered_backoff()(client.create_document)
                create_document(
                    Content=json.dumps(content, sort_keys=True),
                    DocumentFormat="JSON",
                    DocumentType=module.params["document_type"],
                    Name=module.params["name"],
                )
            else:
                update_document = AWSRetry.jittered_backoff()(client.update_document)
                update_document(
                    Content=json.dumps(content, sort_keys=True),
                    DocumentFormat="JSON",
                    DocumentVersion=module.params["document_version"],
                    Name=module.params["name"],
                )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to manage AWS Systems Manager document {module.params['name']}",
            )
        current = get_document(client, module)
    elif changed and module.check_mode:
        current = desired

    result = {
        "changed": changed,
        "document": current,
        "name": module.params["name"],
        "state": "present",
    }

    module.exit_json(**result)


def ensure_absent(client, module):
    current = get_document(client, module)
    changed = current is not None

    if changed and not module.check_mode:
        delete_document = AWSRetry.jittered_backoff()(client.delete_document)
        try:
            delete_document(Name=module.params["name"])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Systems Manager document {module.params['name']}",
            )

    module.exit_json(
        changed=changed,
        name=module.params["name"],
        state="absent",
    )


def main():
    argument_spec = {
        "content": {"type": "dict"},
        "document_type": {"type": "str"},
        "document_version": {"default": "$LATEST", "type": "str"},
        "name": {"required": True, "type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["content", "document_type"])],
        supports_check_mode=True,
    )
    client = module.client("ssm")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
