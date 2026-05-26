#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota
short_description: Manage aws service quotas
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

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def main():
    argument_spec = {
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
        "value": {"required": True, "type": "float"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client(
        "service-quotas", retry_decorator=AWSRetry.jittered_backoff()
    )

    quota_request = {
        "QuotaCode": module.params["quota_code"],
        "ServiceCode": module.params["service_code"],
    }
    current_quota = client.get_service_quota(**quota_request, aws_retry=True).get(
        "Quota", {}
    )
    pending_requests = []
    for status in ("CASE_OPENED", "PENDING"):
        pending_requests.extend(
            paginated_query_with_retries(
                client,
                "list_requested_service_quota_change_history_by_quota",
                **dict(quota_request, Status=status),
            ).get("RequestedQuotas", [])
        )

    desired_value = module.params["value"]
    current_quota_details = boto3_resource_to_ansible_dict(
        current_quota,
        transform_tags=False,
        force_tags=False,
    )
    current_value = current_quota_details.get("value")
    has_pending_request = bool(pending_requests)
    changed = (
        not has_pending_request
        and current_value is not None
        and desired_value > current_value
    )

    requested_quota = None
    if changed:
        if module.check_mode:
            requested_quota = scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "desired_value": desired_value,
                        "global_quota": current_quota_details.get("global_quota"),
                        "quota_arn": current_quota_details.get("quota_arn"),
                        "quota_code": module.params["quota_code"],
                        "quota_name": current_quota_details.get("quota_name"),
                        "service_code": module.params["service_code"],
                        "service_name": current_quota_details.get("service_name"),
                        "status": "PENDING",
                        "unit": current_quota_details.get("unit"),
                    },
                    capitalize_first=True,
                )
            )
        else:
            try:
                requested_quota = client.request_service_quota_increase(
                    **dict(quota_request, DesiredValue=desired_value),
                    aws_retry=True,
                ).get("RequestedQuota")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to request AWS service quota increase for "
                        f"{module.params['quota_code']} for service "
                        f"{module.params['service_code']}"
                    ),
                )

    module.exit_json(
        changed=changed,
        current_quota=current_quota_details,
        pending_requests=boto3_resource_list_to_ansible_dict(
            pending_requests, transform_tags=False, force_tags=False
        ),
        requested_quota=boto3_resource_to_ansible_dict(
            requested_quota, transform_tags=False, force_tags=False
        ),
        quota_code=module.params["quota_code"],
        service_code=module.params["service_code"],
    )


if __name__ == "__main__":
    main()
