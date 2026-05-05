#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

INVALID_DOCUMENT_ERRORS = ("InvalidDocument", "InvalidDocumentOperation")


def get_document(
    client,
    module,
    name,
    document_version="$LATEST",
    missing_document=None,
    default_content=None,
    fail_on_invalid_content=True,
    include_missing_content=False,
):
    get_document = AWSRetry.jittered_backoff()(client.get_document)
    try:
        response = get_document(
            DocumentFormat="JSON",
            DocumentVersion=document_version,
            Name=name,
        )
    except is_boto3_error_code(INVALID_DOCUMENT_ERRORS):
        return missing_document
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to get AWS Systems Manager document {name}"
        )

    document = boto3_resource_to_ansible_dict(response, force_tags=False)
    content = response.get("Content")
    if content is None:
        if default_content is not None or include_missing_content:
            document["content"] = default_content
        return document

    try:
        document["content"] = boto3_resource_to_ansible_dict(
            json.loads(content),
            transform_tags=False,
            force_tags=False,
        )
    except ValueError as e:
        if fail_on_invalid_content:
            module.fail_json(
                msg=f"Unable to parse AWS Systems Manager document content for {name}",
                error=str(e),
            )
        document["content"] = content
    return document


def list_associations(client, module):
    try:
        response = paginated_query_with_retries(client, "list_associations")
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Systems Manager associations")

    return response.get("Associations", [])


def normalize_association(association):
    return boto3_resource_to_ansible_dict(
        association,
        force_tags=False,
        ignore_list=["TargetMaps"],
    )
