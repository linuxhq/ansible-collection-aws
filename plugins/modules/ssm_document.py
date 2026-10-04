#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document
version_added: '1.9.0'
short_description: Manage AWS Systems Manager documents
description:
  - Manages AWS Systems Manager documents.
  - Supports creating, updating, and deleting JSON documents.
  - Content updates create a new document version and promote it to the
    default version once AWS reports it as active.
  - Content is sent and compared exactly as provided, with the AWS document
    schema field names, and is returned exactly as AWS stores it.
  - O(document_type) is immutable after creation.
  - A document that is being created or updated is waited on before it is
    compared, and a document that is being deleted is waited on and created
    again.
  - A document whose AWS status is C(Failed) with the requested content fails
    with the AWS status information.
author:
  - Taylor Kimball (@tkimball83)
options:
  content:
    description:
      - The document content to manage, using the AWS document schema field
        names, for example C(schemaVersion) and C(mainSteps).
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
      - V($LATEST) reconciles against the newest document version, while
        V($DEFAULT) reconciles against the effective default version.
      - Matching V($LATEST) content is promoted when it is not the default version.
    default: $LATEST
    type: str
  force:
    description:
      - Whether to force the deletion of a document when O(state=absent).
      - AWS requires this for some document types, such as
        V(ApplicationConfigurationSchema).
    default: false
    type: bool
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
  wait:
    description:
      - Whether to wait for a created document to become active, or for a
        deleted document to be removed.
      - An updated document version is always waited on before it is promoted
        to the default version.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts.
      - This must be 1 or greater.
    default: 5
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait.
      - When O(state=present), this also applies while an updated document
        version is promoted, regardless of O(wait).
      - This must be 1 or greater.
    default: 300
    type: int
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
    description: The module reports the document that would result from the requested changes.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Ensure a Session Manager document is present
  linuxhq.aws.ssm_document:
    content:
      schemaVersion: "1.0"
      description: Document to hold regional settings for Session Manager
      sessionType: Standard_Stream
      inputs:
        idleSessionTimeout: "60"
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
  contains:
    content:
      description:
        - Document content, parsed from JSON and returned exactly as AWS stores it.
      returned: always
      type: dict
    document_format:
      description: Document format.
      returned: when available
      type: str
    document_type:
      description: Document type.
      returned: always
      type: str
    document_version:
      description: Document version.
      returned: when available
      type: str
    name:
      description: Document name.
      returned: always
      type: str
    status:
      description: Document status.
      returned: when available
      type: str
    status_information:
      description: Details about the document status, such as why it failed.
      returned: when returned by AWS
      type: str
    tags:
      description: Document tags.
      returned: when O(tags) is supplied
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

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    reconcile_ssm_tags,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
)

SSM_DOCUMENT_RESOURCE_TYPE = "Document"
SSM_DOCUMENT_WAITER_MODEL_DATA = {
    "document_active": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "DescribeDocument",
        "acceptors": [
            {"argument": "Document.Status", "expected": "Active", "matcher": "path", "state": "success"},
            # A failed document is inspected after the wait so its status information can be reported.
            {"argument": "Document.Status", "expected": "Failed", "matcher": "path", "state": "success"},
            {"argument": "Document.Status", "expected": "Creating", "matcher": "path", "state": "retry"},
            {"argument": "Document.Status", "expected": "Updating", "matcher": "path", "state": "retry"},
            {"argument": "Document.Status", "expected": "Deleting", "matcher": "path", "state": "failure"},
        ],
    },
    "document_deleted": {
        "delay": 5,
        "maxAttempts": 60,
        "operation": "DescribeDocument",
        "acceptors": [
            {"expected": "InvalidDocument", "matcher": "error", "state": "success"},
            {"argument": "Document.Status", "expected": "Deleting", "matcher": "path", "state": "retry"},
        ],
    },
}
TRANSITIONAL_STATUSES = ("Creating", "Updating")


def document_description_from_response(module, response, message):
    if not isinstance(response, dict) or not isinstance(response.get("DocumentDescription"), dict):
        module.fail_json(msg=message)

    return response["DocumentDescription"]


def comparable_document(document):
    if document is None:
        return None

    return {
        "content": document_content(document),
        "document_type": document.get("DocumentType"),
    }


def fail_failed_document(module, document):
    name = module.params["name"]
    module.fail_json(
        msg=(
            f"AWS Systems Manager document {name} failed: "
            f"{document.get('StatusInformation') or 'no status information was returned'}"
        )
    )


def wait_for_document(client, module, state, document_version=None):
    """Wait for a document version to settle, failing when it ends in the Failed status."""
    name = module.params["name"]
    request = {"Name": name}
    if document_version:
        request["DocumentVersion"] = document_version

    # The waiter fails on terminal states as well as on timeouts, so the message names neither.
    run_waiter(
        module,
        client,
        SSM_DOCUMENT_WAITER_MODEL_DATA,
        f"document_{state}",
        f"Unable to wait for AWS Systems Manager document {name} to become {state}",
        **request,
    )

    if state == "deleted":
        return

    try:
        response = client.describe_document(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to describe AWS Systems Manager document {name}")

    if not isinstance(response, dict) or not isinstance(response.get("Document"), dict):
        module.fail_json(msg=f"Unexpected response while describing AWS Systems Manager document {name}")

    if response["Document"].get("Status") == "Failed":
        fail_failed_document(module, response["Document"])


def ensure_absent(client, module):
    current = get_document(client, module)
    name = module.params["name"]
    changed = current is not None and current.get("Status") != "Deleting"

    if current is not None and not module.check_mode:
        if changed:
            request = {"Name": name}
            if module.params["force"]:
                request["Force"] = True

            try:
                client.delete_document(**request, aws_retry=True)
            except is_boto3_error_code("InvalidDocument"):
                pass
            except is_boto3_error_code("AssociatedInstances") as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        f"Unable to delete AWS Systems Manager document {name} because associations use it; "
                        "delete the associations first"
                    ),
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to delete AWS Systems Manager document {name}")

        if module.params["wait"]:
            wait_for_document(client, module, "deleted")

    module.exit_json(
        changed=changed,
        name=name,
        state="absent",
    )


def current_document(client, module, include_tags):
    """Read the document, settling transitional and deleting states outside check mode."""
    current = get_document(client, module, include_tags=include_tags)
    status = (current or {}).get("Status")

    if status == "Deleting":
        if module.check_mode:
            return None

        wait_for_document(client, module, "deleted")
        return get_document(client, module, include_tags=include_tags)

    if status in TRANSITIONAL_STATUSES and not module.check_mode:
        wait_for_document(client, module, "active", current.get("DocumentVersion"))
        return get_document(client, module, include_tags=include_tags)

    return current


def ensure_present(client, module):
    name = module.params["name"]
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    current = current_document(client, module, include_tags=tags is not None)
    desired_comparable = {
        "content": module.params["content"],
        "document_type": module.params["document_type"],
    }
    current_comparable = comparable_document(current)

    if current is None:
        changed = True
        resource_changed = True
    else:
        if current_comparable["document_type"] != desired_comparable["document_type"]:
            module.fail_json(msg=f"Unable to update AWS Systems Manager document {name}: immutable fields differ")

        changed = current_comparable != desired_comparable
        resource_changed = changed
        if not changed and current.get("Status") == "Failed":
            fail_failed_document(module, current)

    default_version_to_promote = None
    if resource_changed and current is not None and module.params["document_version"] == "$DEFAULT":
        latest = get_document(client, module, document_version="$LATEST")
        if comparable_document(latest) == desired_comparable:
            default_version_to_promote = (latest or {}).get("DocumentVersion")
            if not default_version_to_promote:
                module.fail_json(
                    msg=f"Unable to promote the latest AWS Systems Manager document {name}: AWS returned no document version"
                )

            resource_changed = False

    if current is not None and not resource_changed and module.params["document_version"] == "$LATEST":
        default = get_document(client, module, document_version="$DEFAULT")
        if (default or {}).get("DocumentVersion") != current.get("DocumentVersion"):
            default_version_to_promote = current.get("DocumentVersion")
            if not default_version_to_promote:
                module.fail_json(
                    msg=f"Unable to promote AWS Systems Manager document {name}: AWS returned no document version"
                )

            latest = current
            changed = True

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
            tags,
            purge_tags=purge_tags,
        )

    changed = bool(changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if resource_changed:
            desired_content = json.dumps(desired_comparable["content"], separators=(",", ":"), sort_keys=True)

        if current is None:
            request = {
                "Content": desired_content,
                "DocumentFormat": "JSON",
                "DocumentType": desired_comparable["document_type"],
                "Name": name,
            }
            if tags:
                request["Tags"] = ansible_dict_to_boto3_tag_list(tags)

            try:
                response = client.create_document(**request, aws_retry=True)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to create AWS Systems Manager document {name}")

            current = document_description_from_response(
                module,
                response,
                f"AWS Systems Manager did not return the created document {name}",
            )
            if not current.get("DocumentVersion"):
                module.fail_json(msg=f"AWS Systems Manager did not return the created document {name}")

            if module.params["wait"]:
                wait_for_document(client, module, "active", current["DocumentVersion"])

            current["Content"] = desired_content
            if tags:
                current["Tags"] = request["Tags"]

        elif resource_changed or default_version_to_promote:
            new_version = default_version_to_promote
            if default_version_to_promote:
                current = latest

            if resource_changed:
                try:
                    response = client.update_document(
                        Content=desired_content,
                        DocumentFormat="JSON",
                        DocumentVersion=(
                            "$LATEST"
                            if module.params["document_version"] == "$DEFAULT"
                            else module.params["document_version"]
                        ),
                        Name=name,
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(e, msg=f"Unable to update AWS Systems Manager document {name}")

                updated = document_description_from_response(
                    module,
                    response,
                    f"AWS Systems Manager did not return the updated document {name}",
                )
                new_version = updated.get("DocumentVersion")
                if not new_version:
                    module.fail_json(
                        msg=f"Unable to promote updated AWS Systems Manager document {name}: AWS returned no document version"
                    )

                # A new version can be promoted only after AWS has validated it.
                wait_for_document(client, module, "active", new_version)
                current = dict(current or {}, **updated, Content=desired_content)

            try:
                client.update_document_default_version(
                    DocumentVersion=new_version,
                    Name=name,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to set the default version of AWS Systems Manager document {name}")

        if resource_changed or default_version_to_promote:
            refreshed = get_document(client, module, include_tags=tags is not None)
            if refreshed and comparable_document(refreshed) == desired_comparable:
                current = refreshed

        if current is not None and tags is not None:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )

            reconcile_ssm_tags(
                module,
                client,
                SSM_DOCUMENT_RESOURCE_TYPE,
                name,
                tags_to_set,
                tag_keys_to_unset,
                "AWS Systems Manager document",
            )

            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode:
        current = dict(current or {})
        current.update(
            {
                "Content": desired_comparable["content"],
                "DocumentType": desired_comparable["document_type"],
                "Name": name,
            }
        )
        if tags is not None:
            current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

    document = current
    if (current or {}).get("Name") is not None:
        document = boto3_resource_to_ansible_dict(
            dict(current, Content=document_content(current)),
            ignore_list=["Content"],
            transform_tags=True,
            force_tags=False,
        )

    module.exit_json(
        changed=changed,
        document=document,
        name=name,
        state="present",
    )


def get_document(client, module, include_tags=False, document_version=None):
    name = module.params["name"]

    try:
        document = client.get_document(
            DocumentFormat="JSON",
            DocumentVersion=document_version or module.params["document_version"],
            Name=name,
            aws_retry=True,
        )
    except is_boto3_error_code("InvalidDocument"):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS Systems Manager document {name}")

    if not isinstance(document, dict):
        module.fail_json(msg=f"Unexpected response while getting AWS Systems Manager document {name}")

    content = document.get("Content")
    try:
        parsed_content = json.loads(content) if isinstance(content, str) else None
    except (TypeError, ValueError):
        parsed_content = None

    if not isinstance(parsed_content, dict):
        module.fail_json(msg=f"Unexpected content while getting AWS Systems Manager document {name}")

    document.pop("ResponseMetadata", None)

    if include_tags:
        try:
            response = client.list_tags_for_resource(
                ResourceType=SSM_DOCUMENT_RESOURCE_TYPE,
                ResourceId=name,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e, msg=f"Unable to list tags for AWS Systems Manager {SSM_DOCUMENT_RESOURCE_TYPE} {name}"
            )

        tags = response.get("TagList", []) if isinstance(response, dict) else None
        if not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags):
            module.fail_json(msg=f"Unexpected response while listing tags for AWS Systems Manager document {name}")

        document["Tags"] = tags

    return document


def document_content(document):
    if not document or document.get("Content") is None:
        return {}

    content = document.get("Content")

    if not isinstance(content, str):
        return content

    return json.loads(content)


def main():
    argument_spec = {
        "content": {"type": "dict"},
        "document_type": {"type": "str"},
        "document_version": {"default": "$LATEST", "type": "str"},
        "force": {"default": False, "type": "bool"},
        "name": {"required": True, "type": "str"},
        "purge_tags": {"default": True, "type": "bool"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 5, "type": "int"},
        "wait_timeout": {"default": 300, "type": "int"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["content", "document_type"])],
        supports_check_mode=True,
    )
    state = module.params["state"]
    tags = module.params["tags"]
    require_valid_tags(module, tags if state == "present" else None, 1000)
    # Updated versions are always waited on before they are promoted.
    require_positive_wait_bounds(module, always=state == "present")
    client = module.client(
        "ssm",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["TooManyUpdates"]),
    )

    methods = {"get_document": ("DocumentFormat", "DocumentVersion", "Name")}
    if state == "present":
        methods["create_document"] = (
            "Content",
            "DocumentFormat",
            "DocumentType",
            "Name",
        )
        methods["describe_document"] = ("DocumentVersion", "Name")
        methods["update_document"] = (
            "Content",
            "DocumentFormat",
            "DocumentVersion",
            "Name",
        )
        methods["update_document_default_version"] = ("DocumentVersion", "Name")
        if tags:
            methods["create_document"] += ("Tags",)

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
        methods["delete_document"] = ("Name",) + (("Force",) if module.params["force"] else ())
        if module.params["wait"]:
            methods["describe_document"] = ("Name",)

    require_client_methods(module, client, "Systems Manager", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
