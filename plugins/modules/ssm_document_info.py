#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document_info
version_added: '1.9.0'
short_description: Gather information about AWS Systems Manager documents
description:
  - Gathers information about AWS Systems Manager documents.
  - Retrieves each document in O(document_format). With
    O(document_format=JSON), the returned content is parsed as JSON when
    possible; other content, including C(YAML) written in JSON-compatible
    syntax, is returned exactly as AWS stores it.
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
      - AWS converts between C(JSON) and C(YAML), but cannot return a C(JSON)
        or C(YAML) document as C(TEXT), or a C(TEXT) document as C(JSON) or
        C(YAML).
      - Documents that cannot be returned in this format are omitted from the
        results.
    type: str
  document_version:
    description:
      - The document version to request from the Systems Manager
        C(GetDocument) API.
      - When O(document_version) and O(version_name) are omitted, C($LATEST)
        is requested to preserve the module default behavior.
      - Documents that do not have this version are omitted from the results.
      - Mutually exclusive with O(version_name).
    type: str
  filters:
    description:
      - A dict of filters to apply when listing Systems Manager documents.
      - Filter keys and values are passed to the Systems Manager C(ListDocuments) API.
      - Filter values must not be null.
      - Mutually exclusive with O(name).
    type: dict
  name:
    description:
      - Systems Manager document name used to limit the result set.
      - This must not be empty when provided.
      - A document that does not exist, that does not have the requested
        version, or that cannot be returned in O(document_format) results in
        an empty list.
      - Mutually exclusive with O(filters).
    type: str
  version_name:
    description:
      - The document version name to request from the Systems Manager
        C(GetDocument) API.
      - Documents that do not have this version name are omitted from the
        results.
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
    attachments_content:
      description: The document attachments, including their names, locations, and sizes.
      returned: when the document has attachments
      type: list
      elements: dict
    content:
      description:
        - Document content, parsed from JSON when possible and returned exactly as AWS stores it.
        - Content in the YAML or TEXT format is returned as a string.
      returned: when a document is returned
      type: raw
    created_date:
      description: The date the document was created.
      returned: when available
      type: str
    display_name:
      description: The friendly name of the document version.
      returned: when configured
      type: str
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
    requires:
      description: The documents that this document requires.
      returned: when configured
      type: list
      elements: dict
    review_status:
      description: The review status of the document version.
      returned: when returned by AWS
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
      returned: when a document is returned
      type: dict
    version_name:
      description: The version name of the document version.
      returned: when configured
      type: str
documents:
  description:
    - The AWS Systems Manager documents.
    - Each document includes C(tags) gathered by the module.
  returned: always
  type: list
  elements: dict
  contains:
    attachments_content:
      description: The document attachments, including their names, locations, and sizes.
      returned: when the document has attachments
      type: list
      elements: dict
    content:
      description:
        - Document content, parsed from JSON when possible and returned exactly as AWS stores it.
        - Content in the YAML or TEXT format is returned as a string.
      returned: always
      type: raw
    created_date:
      description: The date the document was created.
      returned: when available
      type: str
    display_name:
      description: The friendly name of the document version.
      returned: when configured
      type: str
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
    requires:
      description: The documents that this document requires.
      returned: when configured
      type: list
      elements: dict
    review_status:
      description: The review status of the document version.
      returned: when returned by AWS
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
      returned: always
      type: dict
    version_name:
      description: The version name of the document version.
      returned: when configured
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
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    SSM_DOCUMENT_RESOURCE_TYPE,
    describe_ssm_document,
    list_ssm_tags,
    require_non_null_ssm_filter_values,
    ssm_filter_list,
)


def content_transform(content, document_format):
    if content is None:
        return {}

    # AWS returns YAML content as stored, so YAML written in JSON-compatible syntax must stay a string too.
    if document_format != "JSON":
        return content

    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content


def format_available(document_format, requested_format):
    # GetDocument converts between JSON and YAML only; TEXT documents are served only as TEXT.
    return (document_format == "TEXT") == (requested_format == "TEXT")


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
    document_format = module.params["document_format"]
    filters = module.params["filters"]
    name = module.params["name"]
    version_name = module.params["version_name"]
    if name == "":
        module.fail_json(msg="name must not be empty")

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    get_request = scrub_none_parameters(
        {
            "DocumentFormat": document_format,
            "DocumentVersion": module.params["document_version"] or (None if version_name else "$LATEST"),
            "VersionName": version_name,
        }
    )
    methods = {
        "get_document": ("Name",) + tuple(get_request),
        "list_tags_for_resource": ("ResourceId", "ResourceType"),
    }
    describe_request = {key: value for key, value in get_request.items() if key != "DocumentFormat"}
    if name is None:
        methods["list_documents"] = ("Filters",) if filters else ()
    else:
        methods["describe_document"] = ("Name",) + tuple(describe_request)

    require_client_methods(
        module,
        client,
        "Systems Manager",
        methods,
    )

    if name:
        # GetDocument reports a format it cannot serve only as a generic ValidationException, so check the format first.
        current = describe_ssm_document(module, client, name, **describe_request)
        document_names = [name] if current and format_available(current["DocumentFormat"], document_format) else []
    else:
        request = {}
        if filters:
            require_non_null_ssm_filter_values(module, filters)
            request["Filters"] = ssm_filter_list(filters)

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

            # ListDocuments returns each document's format, so documents that cannot be served are skipped.
            if format_available(document.get("DocumentFormat"), document_format):
                document_names.append(document_name)

    documents = []
    for document_name in document_names:
        try:
            document = client.get_document(
                **get_request,
                Name=document_name,
                aws_retry=True,
            )
        except is_boto3_error_code(["InvalidDocument", "InvalidDocumentVersion"]):
            # Missing documents and documents without the requested version are omitted.
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS Systems Manager document {document_name}",
            )

        if not isinstance(document, dict):
            module.fail_json(msg=f"Unexpected response while getting AWS Systems Manager document {document_name}")

        document.pop("ResponseMetadata", None)

        tags = list_ssm_tags(
            module,
            client,
            SSM_DOCUMENT_RESOURCE_TYPE,
            document_name,
            "AWS Systems Manager document",
            missing_ok=True,
        )
        if tags is None:
            continue

        document["Tags"] = tags

        documents.append(
            boto3_resource_to_ansible_dict(
                document,
                nested_transforms={"Content": lambda content: content_transform(content, document_format)},
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
