#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota
short_description: Manage aws service quotas
description:
  - Requests AWS service quota increases.
  - Only submits a quota increase request when the desired value is greater than the current applied quota
    and there is no existing open or pending request for the same quota.
  - Falls back to the AWS default quota when the quota has no applied value.
author:
  - Taylor Kimball
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
      - This must be between 0 and 10000000000.
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
    quota_code: L-0263D0A3
    service_code: ec2
    value: 10

- name: Request an IAM quota increase in a specific region
  linuxhq.aws.service_quota:
    quota_code: L-0DA4ABF3
    region: us-east-1
    service_code: iam
    value: 20
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
quota_code:
  description: The managed quota code.
  returned: always
  type: str
requested_quota:
  description:
    - The quota increase request that was submitted or would be submitted in check mode.
  returned: when changed
  type: dict
service_code:
  description: The managed service code.
  returned: always
  type: str
"""

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
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

    if not 0 <= module.params["value"] <= 10000000000:
        module.fail_json(msg="value must be between 0 and 10000000000")

    client = module.client(
        "service-quotas", retry_decorator=AWSRetry.jittered_backoff()
    )

    method_names = {
        "get_aws_default_service_quota",
        "get_service_quota",
        "list_requested_service_quota_change_history_by_quota",
        "request_service_quota_increase",
    }
    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support Service Quotas {method_name}"
            )

    required_method_parameters = {
        "get_aws_default_service_quota": {"QuotaCode", "ServiceCode"},
        "get_service_quota": {"QuotaCode", "ServiceCode"},
        "list_requested_service_quota_change_history_by_quota": {
            "MaxResults",
            "NextToken",
            "QuotaCode",
            "ServiceCode",
            "Status",
        },
        "request_service_quota_increase": {
            "DesiredValue",
            "QuotaCode",
            "ServiceCode",
        },
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Service Quotas "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    quota_code = module.params["quota_code"]
    service_code = module.params["service_code"]
    desired_value = module.params["value"]
    quota_request = {
        "QuotaCode": quota_code,
        "ServiceCode": service_code,
    }

    try:
        current_quota = client.get_service_quota(**quota_request, aws_retry=True).get(
            "Quota", {}
        )
    except is_boto3_error_code("NoSuchResourceException"):
        try:
            current_quota = client.get_aws_default_service_quota(
                **quota_request, aws_retry=True
            ).get("Quota", {})
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to get AWS default service quota "
                    f"{service_code}/{quota_code}"
                ),
            )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS service quota {service_code}/{quota_code}",
        )

    pending_requests = []

    try:
        for status in ("CASE_OPENED", "PENDING"):
            pending_requests.extend(
                paginated_query_with_retries(
                    client,
                    "list_requested_service_quota_change_history_by_quota",
                    **dict(quota_request, Status=status),
                ).get("RequestedQuotas", [])
            )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list AWS service quota change history for "
                f"{service_code}/{quota_code}"
            ),
        )

    current_quota_details = boto3_resource_to_ansible_dict(
        current_quota,
        transform_tags=False,
        force_tags=False,
    )
    current_value = current_quota_details.get("value")

    if current_value is None:
        module.fail_json(
            msg=(
                f"AWS service quota {service_code}/{quota_code} did not "
                "return a value"
            ),
            current_quota=current_quota_details,
        )

    has_pending_request = bool(pending_requests)
    changed = not has_pending_request and desired_value > current_value

    requested_quota = None
    if changed:
        if module.check_mode:
            requested_quota = scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {
                        "desired_value": desired_value,
                        "global_quota": current_quota_details.get("global_quota"),
                        "quota_arn": current_quota_details.get("quota_arn"),
                        "quota_code": quota_code,
                        "quota_name": current_quota_details.get("quota_name"),
                        "service_code": service_code,
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
                        f"{quota_code} for service {service_code}"
                    ),
                )

    result = {
        "changed": changed,
        "current_quota": current_quota_details,
        "pending_requests": boto3_resource_list_to_ansible_dict(
            pending_requests, transform_tags=False, force_tags=False
        ),
        "quota_code": quota_code,
        "service_code": service_code,
    }
    if requested_quota is not None:
        result["requested_quota"] = boto3_resource_to_ansible_dict(
            requested_quota, transform_tags=False, force_tags=False
        )
    module.exit_json(**result)


if __name__ == "__main__":
    main()
