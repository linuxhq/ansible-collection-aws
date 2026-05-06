#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_marker_paginated_find,
    aws_marker_paginated_list,
)


def get_reusable_delegation_set_by_name(client, module, name):
    return aws_marker_paginated_find(
        client,
        module,
        "list_reusable_delegation_sets",
        "DelegationSets",
        lambda delegation_set: delegation_set.get("CallerReference") == name,
        truncated_result="IsTruncated",
    )


def list_reusable_delegation_sets(client, module):
    return aws_marker_paginated_list(
        client,
        module,
        "list_reusable_delegation_sets",
        "DelegationSets",
        truncated_result="IsTruncated",
    )
