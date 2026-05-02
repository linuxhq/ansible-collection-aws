#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule

PENDING_STATUSES = ["CASE_OPENED", "PENDING"]


def get_service_quota(client, module):
    try:
        response = client.get_service_quota(
            QuotaCode=module.params["quota_code"],
            ServiceCode=module.params["service_code"],
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                f"Unable to get AWS service quota {module.params['quota_code']} "
                f"for service {module.params['service_code']}"
            ),
        )
    return response.get("Quota", {})


def list_pending_requests(client, module):
    history = []
    next_token = None

    try:
        while True:
            request = {
                "QuotaCode": module.params["quota_code"],
                "ServiceCode": module.params["service_code"],
            }
            if next_token:
                request["NextToken"] = next_token

            response = client.list_requested_service_quota_change_history_by_quota(
                **request
            )
            history.extend(response.get("RequestedQuotas", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                f"Unable to list AWS service quota requests for {module.params['quota_code']} "
                f"for service {module.params['service_code']}"
            ),
        )
    return [request for request in history if request.get("Status") in PENDING_STATUSES]


def build_requested_quota(module, current_quota):
    requested_quota = {
        "DesiredValue": module.params["value"],
        "QuotaCode": module.params["quota_code"],
        "ServiceCode": module.params["service_code"],
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


def main() -> None:
    argument_spec = {
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
        "value": {"required": True, "type": "float"},
        "validate_certs": {"default": True, "type": "bool"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("service-quotas")

    current_quota = get_service_quota(client, module)
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
            requested_quota = build_requested_quota(module, current_quota)
        else:
            try:
                response = client.request_service_quota_increase(
                    DesiredValue=desired_value,
                    QuotaCode=module.params["quota_code"],
                    ServiceCode=module.params["service_code"],
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        f"Unable to request AWS service quota increase for {module.params['quota_code']} "
                        f"for service {module.params['service_code']}"
                    ),
                )
            requested_quota = response.get("RequestedQuota", {})

    module.exit_json(
        changed=changed,
        current_quota=camel_dict_to_snake_dict(current_quota),
        pending_requests=[
            camel_dict_to_snake_dict(request) for request in pending_requests
        ],
        requested_quota=(
            camel_dict_to_snake_dict(requested_quota) if requested_quota else None
        ),
        quota_code=module.params["quota_code"],
        service_code=module.params["service_code"],
    )


if __name__ == "__main__":
    main()
