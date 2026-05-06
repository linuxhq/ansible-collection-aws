#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.common.collections import is_sequence
from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    normalize_boto3_result,
)

AWS_FIELD_OVERRIDES = {
    "arn": ("ARN", "Arn", "arn"),
    "vpc_id": ("VPCId", "VpcId", "vpcId"),
    "vpc_region": ("VPCRegion", "VpcRegion", "vpcRegion"),
}
AWS_FIELD_NAME_CACHE = dict(AWS_FIELD_OVERRIDES)
JSON_SCALAR_TYPES = (str, int, float, bool)


def _normalized_value(value):
    if value is None or isinstance(value, JSON_SCALAR_TYPES):
        return value
    return normalize_boto3_result(value)


def aws_field_names(field, field_map=None):
    if field_map and field in field_map:
        value = field_map[field]
        if is_sequence(value) or isinstance(value, set):
            return tuple(value)
        return (value,)

    if field not in AWS_FIELD_NAME_CACHE:
        pascal_field = next(
            iter(snake_dict_to_camel_dict({field: None}, capitalize_first=True))
        )
        camel_field = next(iter(snake_dict_to_camel_dict({field: None})))
        AWS_FIELD_NAME_CACHE[field] = tuple(
            dict.fromkeys((pascal_field, camel_field, field))
        )

    return AWS_FIELD_NAME_CACHE[field]


def aws_field_value_from_names(resource, field, aws_fields, prefer_aws_key=True):
    if not prefer_aws_key and field in resource:
        return _normalized_value(resource.get(field))

    for key in aws_fields:
        if key in resource:
            return _normalized_value(resource.get(key))

    if prefer_aws_key and field in resource:
        return _normalized_value(resource.get(field))

    return None


def aws_field_values(resource, fields, defaults=None):
    defaults = defaults or {}
    values = {}
    resource = resource or {}
    for field in fields:
        value = aws_field_value_from_names(
            resource,
            field,
            aws_field_names(field),
        )
        if value is None and field in defaults:
            value = defaults[field]
        if value is not None:
            values[field] = value
    return values
