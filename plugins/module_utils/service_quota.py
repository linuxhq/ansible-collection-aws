#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_resource,
)

PENDING_STATUSES = ("CASE_OPENED", "PENDING")


def get_service_quota(client, module, quota_code=None, service_code=None):
    if quota_code is None:
        quota_code = module.params["quota_code"]
    if service_code is None:
        service_code = module.params["service_code"]

    return aws_resource(
        client,
        module,
        "get_service_quota",
        "Quota",
        default={},
        QuotaCode=quota_code,
        ServiceCode=service_code,
    )


def list_pending_service_quota_requests(
    client, module, quota_code=None, service_code=None
):
    if quota_code is None:
        quota_code = module.params["quota_code"]
    if service_code is None:
        service_code = module.params["service_code"]

    requests = []
    for status in PENDING_STATUSES:
        requests.extend(
            aws_paginated_list(
                client,
                module,
                "list_requested_service_quota_change_history_by_quota",
                "RequestedQuotas",
                QuotaCode=quota_code,
                ServiceCode=service_code,
                Status=status,
            )
        )
    return requests
