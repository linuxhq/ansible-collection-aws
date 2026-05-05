#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota
version_added: 1.9.1
short_description: Manage AWS service quota increase requests
description:
  - Requests AWS service quota increases.
  - Only submits a quota increase request when the desired value is greater than the current applied quota
    and there is no existing open or pending request for the same quota.
author:
  - Taylor Kimball (@tkimball83)
options:
  quota_code:
    description:
      - The quota code to manage.
    required: true
    type: str
  service_code:
    description:
      - The service code that owns the quota.
    required: true
    type: str
  value:
    description:
      - The desired quota value.
    required: true
    type: float
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Request an EC2 quota increase
  linuxhq.aws.service_quota:
    service_code: ec2
    quota_code: L-0263D0A3
    value: 10

- name: Request an IAM quota increase in a specific region
  linuxhq.aws.service_quota:
    service_code: iam
    quota_code: L-0DA4ABF3
    value: 20
    region: us-east-1
"""

RETURN = r"""
current_quota:
  description:
    - The current AWS service quota details.
  returned: always
  type: dict
pending_requests:
  description:
    - Existing open or pending increase requests for the quota.
  returned: always
  type: list
  elements: dict
requested_quota:
  description:
    - The quota increase request that was submitted or would be submitted in check mode.
  returned: when changed
  type: dict
quota_code:
  description: The managed quota code.
  returned: always
  type: str
service_code:
  description: The managed service code.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_list_to_snake_dicts,
    aws_resource_to_snake_dict,
)

PENDING_STATUSES = ("CASE_OPENED", "PENDING")


def build_requested_quota(params, current_quota):
    requested_quota = {
        "DesiredValue": params["value"],
        "QuotaCode": params["quota_code"],
        "ServiceCode": params["service_code"],
    }
    for key in (
        "GlobalQuota",
        "QuotaArn",
        "QuotaName",
        "ServiceName",
        "Unit",
    ):
        if key in current_quota:
            requested_quota[key] = current_quota[key]
    requested_quota["Status"] = "PENDING"
    return requested_quota


def list_pending_requests(client, module, quota_code=None, service_code=None):
    quota_code = quota_code or module.params["quota_code"]
    service_code = service_code or module.params["service_code"]

    return [
        request
        for request in aws_paginated_list(
            client,
            module,
            "list_requested_service_quota_change_history_by_quota",
            "RequestedQuotas",
            QuotaCode=quota_code,
            ServiceCode=service_code,
        )
        if request.get("Status") in PENDING_STATUSES
    ]


def normalize_quotas(quotas):
    return aws_resource_list_to_snake_dicts(quotas)


def main():
    argument_spec = {
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
        "value": {"required": True, "type": "float"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("service-quotas")

    current_quota = aws_resource(
        client,
        module,
        "get_service_quota",
        "Quota",
        default={},
        QuotaCode=module.params["quota_code"],
        ServiceCode=module.params["service_code"],
    )
    pending_requests = list_pending_requests(client, module)

    desired_value = module.params["value"]
    current_value = current_quota.get("Value")
    has_pending_request = bool(pending_requests)
    changed = (
        not has_pending_request
        and current_value is not None
        and desired_value > current_value
    )

    requested_quota = None
    if changed:
        if module.check_mode:
            requested_quota = build_requested_quota(module.params, current_quota)
        else:
            response = aws_response(
                client,
                module,
                "request_service_quota_increase",
                error_message=(
                    "Unable to request AWS service quota increase for "
                    f"{module.params['quota_code']} for service "
                    f"{module.params['service_code']}"
                ),
                DesiredValue=desired_value,
                QuotaCode=module.params["quota_code"],
                ServiceCode=module.params["service_code"],
            )
            requested_quota = response.get("RequestedQuota", {})

    module.exit_json(
        changed=changed,
        current_quota=aws_resource_to_snake_dict(current_quota),
        pending_requests=normalize_quotas(pending_requests),
        requested_quota=(
            aws_resource_to_snake_dict(requested_quota) if requested_quota else None
        ),
        quota_code=module.params["quota_code"],
        service_code=module.params["service_code"],
    )


if __name__ == "__main__":
    main()
