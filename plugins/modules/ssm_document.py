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
author:
  - Taylor Kimball (@tkimball83)
options:
  content:
    description:
      - The document content to manage.
      - Provide the content as structured Ansible YAML data.
      - The module serializes the content to JSON for AWS Systems Manager.
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
      schemaVersion: "1.0"
      description: Document to hold regional settings for Session Manager
      sessionType: Standard_Stream
      inputs:
        idleSessionTimeout: 60
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
proposed_document:
  description:
    - The document values that would exist after the requested change.
  returned: when changed and state is present
  type: dict
state:
  description: The requested state of the document.
  returned: always
  type: str
"""

import json

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in (
        "InvalidDocument",
        "InvalidDocumentOperation",
    )


def build_document_response(metadata, content):
    document = camel_dict_to_snake_dict(metadata or {})
    document["content"] = content
    return document


def build_proposed_document(module):
    return {
        "content": module.params["content"],
        "document_type": module.params["document_type"],
        "name": module.params["name"],
    }


def get_document(client, module):
    try:
        response = client.get_document(
            DocumentFormat="JSON",
            DocumentVersion=module.params["document_version"],
            Name=module.params["name"],
        )
    except Exception as e:
        if is_not_found_error(e):
            return None
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Systems Manager document {module.params['name']}",
        )

    try:
        content = json.loads(response.get("Content", "{}"))
    except ValueError as e:
        module.fail_json(
            msg=f"Unable to parse AWS Systems Manager document content for {module.params['name']}",
            error=str(e),
        )

    return build_document_response(response, content)


def ensure_present(client, module):
    current = get_document(client, module)
    desired = build_proposed_document(module)
    changed = current is None or current.get("content") != module.params["content"]

    if changed and not module.check_mode:
        try:
            if current is None:
                client.create_document(
                    Content=json.dumps(module.params["content"], sort_keys=True),
                    DocumentFormat="JSON",
                    DocumentType=module.params["document_type"],
                    Name=module.params["name"],
                )
            else:
                client.update_document(
                    Content=json.dumps(module.params["content"], sort_keys=True),
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
    if changed:
        result["proposed_document"] = desired

    module.exit_json(**result)


def ensure_absent(client, module):
    current = get_document(client, module)
    changed = current is not None

    if changed and not module.check_mode:
        try:
            client.delete_document(Name=module.params["name"])
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
