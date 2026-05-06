#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import json

from ansible_collections.linuxhq.aws.plugins.module_utils.fields import (
    aws_field_names,
    aws_field_value_from_names,
)


def _canonical_item_key(item):
    return json.dumps(item, separators=(",", ":"), sort_keys=True)


def _field_differences(current, desired, fields, field_map=None):
    current = current or {}
    desired = desired or {}
    differences = {}
    for field in fields:
        field_names = aws_field_names(field, field_map)
        difference = {
            "current": aws_field_value_from_names(
                current,
                field,
                field_names,
                prefer_aws_key=True,
            ),
            "desired": aws_field_value_from_names(
                desired,
                field,
                field_names,
                prefer_aws_key=False,
            ),
        }
        if difference["current"] != difference["desired"]:
            differences[field] = difference
    return differences


def _normalized_items(items, normalizer=None):
    return [
        normalizer(item) if normalizer is not None else item for item in items or []
    ]


def canonicalize_list(items, normalizer=None, sort_key=None):
    normalized = _normalized_items(items, normalizer)
    return sorted(normalized, key=sort_key or _canonical_item_key)


def fail_on_immutable_differences(
    module,
    differences,
    immutable_fields,
    msg="Immutable fields differ",
):
    immutable_field_set = set(immutable_fields)
    immutable_differences = {
        field: difference
        for field, difference in differences.items()
        if field in immutable_field_set
    }
    if immutable_differences:
        module.fail_json(
            msg=msg,
            immutable_items=immutable_fields,
            differences=immutable_differences,
        )


def field_differences(current, desired, fields, field_map=None):
    differences = _field_differences(current, desired, fields, field_map)
    return differences, bool(differences)


def list_difference(left, right, normalizer=None, sort_key=None):
    right_keys = {
        _canonical_item_key(item) for item in _normalized_items(right, normalizer)
    }
    left_item_keys = []
    for item in _normalized_items(left, normalizer):
        item_key = _canonical_item_key(item)
        if item_key not in right_keys:
            left_item_keys.append((item_key, item))

    if sort_key is not None:
        return sorted((item for _item_key, item in left_item_keys), key=sort_key)

    left_item_keys.sort(key=lambda item_key: item_key[0])
    return [item for _key, item in left_item_keys]


def validate_immutable_fields(
    module,
    current,
    desired,
    immutable_fields,
    msg="Immutable fields differ",
    field_map=None,
):
    immutable_differences = {
        field: difference
        for field, difference in _field_differences(
            current,
            desired,
            immutable_fields,
            field_map,
        ).items()
        if difference["current"] is not None and difference["desired"] is not None
    }
    fail_on_immutable_differences(
        module,
        immutable_differences,
        immutable_fields,
        msg,
    )
