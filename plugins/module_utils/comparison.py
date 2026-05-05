#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def aws_resource_to_snake_dict(resource, ignore_list=None):
    return boto3_resource_to_ansible_dict(
        resource,
        transform_tags=False,
        force_tags=False,
        ignore_list=ignore_list,
    )


def aws_resource_list_to_snake_dicts(resources, ignore_list=None):
    return boto3_resource_list_to_ansible_dict(
        resources,
        transform_tags=False,
        force_tags=False,
        ignore_list=ignore_list,
    )


def aws_resource_matches(resource, **criteria):
    comparable = aws_resource_to_snake_dict(resource)
    return all(comparable.get(field) == value for field, value in criteria.items())


def find_aws_resource(resources, **criteria):
    for resource in resources:
        if aws_resource_matches(resource, **criteria):
            return resource
    return None


def filter_aws_resources(resources, **criteria):
    return [
        resource for resource in resources if aws_resource_matches(resource, **criteria)
    ]


def _canonical_item_key(item):
    return json.dumps(item, sort_keys=True)


def canonicalize_list(items, normalizer=None, sort_key=None):
    normalized = [
        normalizer(item) if normalizer is not None else item for item in items or []
    ]
    return sorted(normalized, key=sort_key or _canonical_item_key)


def list_difference(left, right, normalizer=None, sort_key=None):
    right_keys = {
        _canonical_item_key(item)
        for item in canonicalize_list(right, normalizer, sort_key)
    }
    return [
        item
        for item in canonicalize_list(left, normalizer, sort_key)
        if _canonical_item_key(item) not in right_keys
    ]


def _field_difference(current, desired, field):
    return {
        "current": current.get(field),
        "desired": desired.get(field),
    }


def _field_differences(current, desired, fields):
    current = aws_resource_to_snake_dict(current)
    desired = aws_resource_to_snake_dict(desired)

    return {
        field: _field_difference(current, desired, field)
        for field in fields
        if current.get(field) != desired.get(field)
    }


def _immutable_field_differences(current, desired, immutable_fields):
    current = aws_resource_to_snake_dict(current)
    desired = aws_resource_to_snake_dict(desired)
    if not current or not desired:
        return {}

    return {
        field: _field_difference(current, desired, field)
        for field in immutable_fields
        if current.get(field) is not None
        and desired.get(field) is not None
        and current[field] != desired[field]
    }


def validate_immutable_fields(module, current, desired, immutable_fields, msg=None):
    _fail_on_immutable_differences(
        module,
        _immutable_field_differences(current, desired, immutable_fields),
        immutable_fields,
        msg or "Immutable fields differ",
    )


def validated_field_differences(
    module,
    current,
    desired,
    fields,
    immutable_fields=None,
    msg=None,
):
    differences = _field_differences(current, desired, fields)
    _fail_on_immutable_differences(
        module,
        differences,
        immutable_fields or [],
        msg or "Immutable fields differ",
    )
    return differences, bool(differences)


def _fail_on_immutable_differences(module, differences, immutable_fields, msg):
    immutable_differences = {
        field: difference
        for field, difference in differences.items()
        if field in immutable_fields
    }
    if immutable_differences:
        module.fail_json(
            msg=msg,
            immutable_items=immutable_fields,
            differences=immutable_differences,
        )
