#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document_info
version_added: "1.9.5"
short_description: Gather information about AWS Systems Manager documents
description:
  - Gathers information about AWS Systems Manager documents.
  - Retrieves each document as JSON and parses the returned content when possible.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when listing Systems Manager documents.
      - Filter keys and values are passed to the Systems Manager C(ListDocuments) API.
    type: dict
  names:
    description:
      - Systems Manager document names used to limit the result set.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about a Systems Manager document
  linuxhq.aws.ssm_document_info:
    names:
      - molecule-command-shell

- name: Gather information about Systems Manager documents using filters
  linuxhq.aws.ssm_document_info:
    filters:
      DocumentType: Command
"""

RETURN = r"""
document:
  description:
    - The first AWS Systems Manager document, when one document is returned.
  returned: always
  type: dict
documents:
  description:
    - The AWS Systems Manager documents.
  returned: always
  type: list
  elements: dict
"""

import json

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

SSM_DOCUMENT_RESOURCE_TYPE = "Document"


def ssm_filter_list(filters):
    return [
        {
            "Key": key,
            "Values": value if isinstance(value, list) else [value],
        }
        for key, value in (filters or {}).items()
    ]


def get_document(client, module, name):
    try:
        document = client.get_document(
            DocumentFormat="JSON",
            DocumentVersion="$LATEST",
            Name=name,
            aws_retry=True,
        )
    except is_boto3_error_code(("InvalidDocument", "InvalidDocumentOperation")):
        return {}
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Systems Manager document {name}",
        )
    if document:
        try:
            document["Tags"] = client.list_tags_for_resource(
                ResourceType=SSM_DOCUMENT_RESOURCE_TYPE,
                ResourceId=name,
                aws_retry=True,
            ).get("TagList", [])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list tags for AWS Systems Manager document {name}",
            )
    return document


def content_transform(content):
    if content is None:
        return {}
    try:
        content = json.loads(content)
    except ValueError:
        return content
    if isinstance(content, dict):
        return boto3_resource_to_ansible_dict(
            content, transform_tags=False, force_tags=False
        )
    return content


def normalized_document(document):
    return boto3_resource_to_ansible_dict(
        document,
        nested_transforms={"Content": content_transform},
        transform_tags=True,
        force_tags=False,
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "filters": {"type": "dict"},
            "names": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    if module.params["names"]:
        document_names = module.params["names"]
    else:
        request = {}
        if module.params["filters"]:
            request["Filters"] = ssm_filter_list(module.params["filters"])
        document_names = [
            document["Name"]
            for document in paginated_query_with_retries(
                client,
                "list_documents",
                **request,
            ).get("DocumentIdentifiers", [])
            if document.get("Name")
        ]

    documents = [
        normalized_document(document)
        for document in [get_document(client, module, name) for name in document_names]
        if document
    ]

    module.exit_json(
        changed=False,
        document=documents[0] if len(documents) == 1 else {},
        documents=documents,
    )


if __name__ == "__main__":
    main()
