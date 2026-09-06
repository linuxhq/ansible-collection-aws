#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document_info
short_description: Gather information about AWS Systems Manager documents
description:
  - Gathers information about AWS Systems Manager documents.
  - Retrieves each document as JSON and parses the returned content when possible.
author:
  - Taylor Kimball (@tkimball83)
options:
  document_format:
    choices:
      - JSON
      - TEXT
      - YAML
    default: JSON
    description:
      - The document format to request from the Systems Manager
        C(GetDocument) API.
    type: str
  document_version:
    description:
      - The document version to request from the Systems Manager
        C(GetDocument) API.
      - Mutually exclusive with O(version_name).
      - When O(document_version) and O(version_name) are omitted, C($LATEST)
        is requested to preserve the module default behavior.
    type: str
  filters:
    description:
      - A dict of filters to apply when listing Systems Manager documents.
      - Filter keys and values are passed to the Systems Manager C(ListDocuments) API.
      - Mutually exclusive with O(name).
    type: dict
  name:
    description:
      - Systems Manager document name used to limit the result set.
      - This must not be empty when provided.
      - A document that does not exist results in an empty list.
      - Mutually exclusive with O(filters).
    type: str
  version_name:
    description:
      - The document version name to request from the Systems Manager
        C(GetDocument) API.
      - Mutually exclusive with O(document_version).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about a Systems Manager document
  linuxhq.aws.ssm_document_info:
    name: molecule-command-shell

- name: Gather information about Systems Manager documents using filters
  linuxhq.aws.ssm_document_info:
    filters:
      DocumentType: Command

- name: Gather information about a named Systems Manager document version
  linuxhq.aws.ssm_document_info:
    name: molecule-command-shell
    version_name: production
"""

RETURN = r"""
document:
  description:
    - The first AWS Systems Manager document, when one document is returned.
  returned: always
  type: dict
  contains:
    content:
      description: Document content.
      returned: when a document is returned
      type: raw
    document_format:
      description: Document format.
      returned: when a document is returned
      type: str
    document_type:
      description: Document type.
      returned: when a document is returned
      type: str
    document_version:
      description: Document version.
      returned: when a document is returned
      type: str
    name:
      description: Document name.
      returned: when a document is returned
      type: str
    tags:
      description: Document tags.
      returned: when a document is returned
      type: dict
documents:
  description:
    - The AWS Systems Manager documents.
    - Each document includes C(tags) gathered by the module.
  returned: always
  type: list
  elements: dict
  contains:
    content:
      description: Document content.
      returned: always
      type: raw
    document_format:
      description: Document format.
      returned: always
      type: str
    document_type:
      description: Document type.
      returned: always
      type: str
    document_version:
      description: Document version.
      returned: always
      type: str
    name:
      description: Document name.
      returned: always
      type: str
    tags:
      description: Document tags.
      returned: always
      type: dict
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
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)

SSM_DOCUMENT_RESOURCE_TYPE = "Document"


def content_transform(content):
    if content is None:
        return {}

    try:
        content = json.loads(content)
    except (TypeError, ValueError):
        return content

    if isinstance(content, dict):
        return boto3_resource_to_ansible_dict(content, transform_tags=False, force_tags=False)

    return content


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "document_format": {
                "choices": ["JSON", "TEXT", "YAML"],
                "default": "JSON",
                "type": "str",
            },
            "document_version": {"type": "str"},
            "filters": {"type": "dict"},
            "name": {"type": "str"},
            "version_name": {"type": "str"},
        },
        mutually_exclusive=[
            ["document_version", "version_name"],
            ["filters", "name"],
        ],
        supports_check_mode=True,
    )
    filters = module.params["filters"]
    name = module.params["name"]
    version_name = module.params["version_name"]
    if name == "":
        module.fail_json(msg="name must not be empty")

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    get_request = scrub_none_parameters(
        {
            "DocumentFormat": module.params["document_format"],
            "DocumentVersion": module.params["document_version"] or (None if version_name else "$LATEST"),
            "VersionName": version_name,
        }
    )
    methods = {
        "get_document": ("Name",) + tuple(get_request),
        "list_tags_for_resource": ("ResourceId", "ResourceType"),
    }
    if name is None:
        methods["list_documents"] = ("Filters",) if filters else ()

    require_client_methods(
        module,
        client,
        "Systems Manager",
        methods,
    )

    if name:
        document_names = [name]
    else:
        request = {}
        if filters:
            request["Filters"] = []
            for key, value in filters.items():
                values = value if isinstance(value, list) else [value]
                request["Filters"].append(
                    {
                        "Key": key,
                        "Values": [str(item) for item in values],
                    }
                )

        document_identifiers = query_list(
            module,
            client,
            "list_documents",
            "DocumentIdentifiers",
            "Unable to list AWS Systems Manager documents",
            **request,
        )

        document_names = []
        for document in document_identifiers:
            document_name = document.get("Name") if isinstance(document, dict) else None
            if not isinstance(document_name, str) or not document_name:
                module.fail_json(msg="Unexpected response while listing AWS Systems Manager documents")

            document_names.append(document_name)

    documents = []
    for document_name in document_names:
        try:
            document = client.get_document(
                **get_request,
                Name=document_name,
                aws_retry=True,
            )
        except is_boto3_error_code("InvalidDocument"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS Systems Manager document {document_name}",
            )

        if not isinstance(document, dict):
            module.fail_json(msg=f"Unexpected response while getting AWS Systems Manager document {document_name}")

        document.pop("ResponseMetadata", None)

        try:
            response = client.list_tags_for_resource(
                ResourceType=SSM_DOCUMENT_RESOURCE_TYPE,
                ResourceId=document_name,
                aws_retry=True,
            )
        except is_boto3_error_code("InvalidResourceId"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to list tags for AWS Systems Manager document " f"{document_name}"),
            )

        tags = response.get("TagList", []) if isinstance(response, dict) else None
        if not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags):
            module.fail_json(
                msg=f"Unexpected response while listing tags for AWS Systems Manager document {document_name}"
            )

        document["Tags"] = tags

        documents.append(
            boto3_resource_to_ansible_dict(
                document,
                nested_transforms={"Content": content_transform},
                transform_tags=True,
                force_tags=False,
            )
        )

    module.exit_json(
        changed=False,
        document=documents[0] if len(documents) == 1 else {},
        documents=documents,
    )


if __name__ == "__main__":
    main()
