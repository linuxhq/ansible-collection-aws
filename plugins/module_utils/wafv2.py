#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_marker_paginated_list,
    aws_resource,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
)


def _list_wafv2_resources(
    client,
    module,
    scope,
    list_operation,
    list_result_key,
    get_operation,
    get_result_key,
):
    summaries = aws_marker_paginated_list(
        client,
        module,
        list_operation,
        list_result_key,
        marker_arg="NextMarker",
        initial_kwargs={"Limit": 100, "Scope": scope},
    )
    return aws_resource_list_to_snake_dicts(
        [
            aws_resource(
                client,
                module,
                get_operation,
                get_result_key,
                default={},
                Id=summary["Id"],
                Name=summary["Name"],
                Scope=scope,
            )
            for summary in summaries
            if summary.get("Id") and summary.get("Name")
        ]
    )


def list_wafv2_ip_sets(client, module, scope):
    return _list_wafv2_resources(
        client,
        module,
        scope,
        "list_ip_sets",
        "IPSets",
        "get_ip_set",
        "IPSet",
    )


def list_wafv2_web_acls(client, module, scope):
    return _list_wafv2_resources(
        client,
        module,
        scope,
        "list_web_acls",
        "WebACLs",
        "get_web_acl",
        "WebACL",
    )
