#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json

from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_find,
    aws_paginated_list,
    aws_request_params_list,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
)

INVALID_DOCUMENT_ERRORS = ("InvalidDocument", "InvalidDocumentOperation")


def _document_content_value(content, strict=True):
    if content is None:
        return {}
    if not isinstance(content, str):
        return content

    try:
        return json.loads(content)
    except ValueError:
        if strict:
            raise
        return content


def aws_ssm_targets(targets, default_values=False, none_if_omitted=False):
    if targets is None:
        return None if none_if_omitted else []
    if default_values:
        targets = [
            dict(target, values=target.get("values") or []) for target in targets
        ]
    return aws_request_params_list(targets)


def get_ssm_association_by_name(client, module, name):
    return aws_paginated_find(
        client,
        module,
        "list_associations",
        "Associations",
        lambda association: association.get("Name") == name,
        AssociationFilterList=[{"key": "Name", "value": name}],
    )


def get_ssm_document(client, module, name, document_version="$LATEST", default=None):
    return aws_response(
        client,
        module,
        "get_document",
        ignore_error_codes=INVALID_DOCUMENT_ERRORS,
        ignored_error_result=default,
        DocumentFormat="JSON",
        DocumentVersion=document_version,
        Name=name,
    )


def list_ssm_associations(client, module, name=None):
    kwargs = {}
    if name is not None:
        kwargs["AssociationFilterList"] = [{"key": "Name", "value": name}]

    return aws_paginated_list(
        client,
        module,
        "list_associations",
        "Associations",
        **kwargs,
    )


def normalize_ssm_association(association):
    return aws_resource_to_snake_dict(association, ignore_list=["TargetMaps"])


def normalize_ssm_document(document, strict_content=True, force_content=False):
    if not document:
        return document

    def content_transform(content):
        content = _document_content_value(content, strict_content)
        if isinstance(content, dict):
            return aws_resource_to_snake_dict(content)
        return content

    result = aws_resource_to_snake_dict(
        document,
        nested_transforms={"Content": content_transform},
    )
    if force_content and "content" not in result:
        result["content"] = {}
    return result


def ssm_document_content(document, strict=True):
    document = document or {}
    return _document_content_value(
        document.get("Content", document.get("content")),
        strict,
    )
