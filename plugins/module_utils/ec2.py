#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    sanitize_filters_to_boto3_filter_list,
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_find,
    aws_paginated_list,
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.fields import (
    aws_field_values,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
    aws_resource_to_snake_dict,
)


def describe_managed_prefix_lists(client, module, name=None):
    return aws_paginated_list(
        client,
        module,
        "describe_managed_prefix_lists",
        "PrefixLists",
        **ec2_filter_request({"prefix_list_name": name}),
    )


def ec2_filter_request(filters):
    filters = scrub_none_parameters(filters)
    return (
        {"Filters": sanitize_filters_to_boto3_filter_list(filters)} if filters else {}
    )


def get_customer_managed_prefix_list_by_name(client, module, name):
    return aws_paginated_find(
        client,
        module,
        "describe_managed_prefix_lists",
        "PrefixLists",
        lambda prefix_list: (
            prefix_list.get("PrefixListName") == name
            and prefix_list.get("OwnerId") != "AWS"
        ),
        **ec2_filter_request({"prefix_list_name": name}),
    )


def get_instance_metadata_defaults(client, module):
    return aws_resource_to_snake_dict(
        aws_resource(
            client,
            module,
            "get_instance_metadata_defaults",
            "AccountLevel",
            default={},
        )
    )


def get_managed_prefix_list_entries(client, module, prefix_list_id):
    return aws_paginated_list(
        client,
        module,
        "get_managed_prefix_list_entries",
        "Entries",
        PrefixListId=prefix_list_id,
    )


def get_serial_console_access_status(client, module):
    response = aws_response(client, module, "get_serial_console_access_status")
    return aws_field_values(
        response,
        ("managed_by", "serial_console_access_enabled"),
    )


def normalize_managed_prefix_list(prefix_list, entries=None):
    normalized = aws_resource_to_snake_dict(prefix_list or {})
    if entries is not None:
        normalized["entries"] = aws_resource_list_to_snake_dicts(entries)
    return normalized
