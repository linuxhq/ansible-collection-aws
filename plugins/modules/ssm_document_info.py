#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document_info
short_description: Gather information about aws systems manager documents
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
      - When O(document_version) and O(version_name) are omitted, C($LATEST)
        is requested to preserve the module default behavior.
    type: str
  filters:
    description:
      - A dict of filters to apply when listing Systems Manager documents.
      - Filter keys and values are passed to the Systems Manager C(ListDocuments) API.
    type: dict
  name:
    description:
      - Systems Manager document name used to limit the result set.
    type: str
  version_name:
    description:
      - The document version name to request from the Systems Manager
        C(GetDocument) API.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
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
        mutually_exclusive=[["document_version", "version_name"]],
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    if module.params["name"]:
        document_names = [module.params["name"]]
    else:
        request = {}
        if module.params["filters"]:
            request["Filters"] = []
            for key, value in module.params["filters"].items():
                request["Filters"].append(
                    {
                        "Key": key,
                        "Values": value if isinstance(value, list) else [value],
                    }
                )

        try:
            document_identifiers = paginated_query_with_retries(
                client,
                "list_documents",
                **request,
            ).get("DocumentIdentifiers", [])
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to list AWS Systems Manager documents")

        document_names = []
        for document in document_identifiers:
            if document.get("Name"):
                document_names.append(document["Name"])

    documents = []
    for name in document_names:
        version_name = module.params["version_name"]
        request = {
            "DocumentFormat": module.params["document_format"],
            "DocumentVersion": module.params["document_version"]
            or (None if version_name else "$LATEST"),
            "Name": name,
            "VersionName": version_name,
        }
        for key in list(request):
            if request[key] is None:
                del request[key]

        try:
            document = client.get_document(
                **request,
                aws_retry=True,
            )
        except is_boto3_error_code(("InvalidDocument", "InvalidDocumentOperation")):
            continue
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS Systems Manager document {name}",
            )

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
