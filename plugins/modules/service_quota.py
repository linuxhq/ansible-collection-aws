#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota
short_description: Manage AWS service quotas
description:
  - Requests AWS service quota increases.
  - Only submits a quota increase request when the desired value is greater than the current applied quota
    and there is no existing open or pending request for the same quota.
  - Falls back to the AWS default quota when the quota has no applied value.
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
      - This must be between 0 and 10000000000.
    required: true
    type: float
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Determines what changes would occur without modifying AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
  contains:
    value:
      description: The current quota value.
      returned: always
      type: float
pending_requests:
  description:
    - Existing open or pending increase requests for the quota.
  returned: always
  type: list
  elements: dict
  contains:
    desired_value:
      description: The requested quota value.
      returned: always
      type: float
    status:
      description: The request status.
      returned: always
      type: str
quota_code:
  description: The managed quota code.
  returned: always
  type: str
requested_quota:
  description:
    - The quota increase request that was submitted or would be submitted in check mode.
  returned: when changed
  type: dict
  contains:
    desired_value:
      description: The requested quota value.
      returned: always
      type: float
service_code:
  description: The managed service code.
  returned: always
  type: str
"""

import math

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def response_resource(module, response, key, description):
    if not isinstance(response, dict) or not isinstance(response.get(key), dict):
        module.fail_json(msg=f"AWS Service Quotas returned an invalid {description} response")

    return response[key]


def response_resources(module, response, key, description):
    if not isinstance(response, dict) or not isinstance(response.get(key, []), list):
        module.fail_json(msg=f"AWS Service Quotas returned an invalid {description} response")

    resources = response.get(key, [])
    if any(not isinstance(resource, dict) for resource in resources):
        module.fail_json(msg=f"AWS Service Quotas returned an invalid {description} entry")

    return resources


def validate_current_quota(module, quota, service_code, quota_code):
    for key, expected in (("ServiceCode", service_code), ("QuotaCode", quota_code)):
        if key in quota and quota[key] != expected:
            module.fail_json(msg=f"AWS Service Quotas returned a mismatched quota for {service_code}/{quota_code}")

    value = quota.get("Value")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or isinstance(value, float)
        and not math.isfinite(value)
    ):
        module.fail_json(msg=f"AWS service quota {service_code}/{quota_code} did not return a valid value")


def validate_quota_request(module, request, service_code, quota_code, desired_value=None, status=None):
    if not request:
        module.fail_json(msg=f"AWS Service Quotas returned an invalid request for {service_code}/{quota_code}")

    expected_values = {
        "ServiceCode": service_code,
        "QuotaCode": quota_code,
        "DesiredValue": desired_value,
        "Status": status,
    }
    if any(
        key in request and expected is not None and request[key] != expected
        for key, expected in expected_values.items()
    ):
        module.fail_json(msg=f"AWS Service Quotas returned a mismatched request for {service_code}/{quota_code}")

    if status is not None and request.get("Status") != status:
        module.fail_json(msg=f"AWS Service Quotas returned an invalid request for {service_code}/{quota_code}")


def main():
    argument_spec = {
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
        "value": {"required": True, "type": "float"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)

    if not math.isfinite(module.params["value"]) or not 0 <= module.params["value"] <= 10000000000:
        module.fail_json(msg="value must be between 0 and 10000000000")

    client = module.client("service-quotas", retry_decorator=AWSRetry.jittered_backoff())

    methods = {
        "get_aws_default_service_quota": ("QuotaCode", "ServiceCode"),
        "get_service_quota": ("QuotaCode", "ServiceCode"),
        "list_requested_service_quota_change_history_by_quota": (
            "MaxResults",
            "NextToken",
            "QuotaCode",
            "ServiceCode",
            "Status",
        ),
    }
    if not module.check_mode:
        methods["request_service_quota_increase"] = (
            "DesiredValue",
            "QuotaCode",
            "ServiceCode",
        )

    require_client_methods(module, client, "Service Quotas", methods)

    quota_code = module.params["quota_code"]
    service_code = module.params["service_code"]
    desired_value = module.params["value"]
    quota_request = {
        "QuotaCode": quota_code,
        "ServiceCode": service_code,
    }

    try:
        response = client.get_service_quota(**quota_request, aws_retry=True)
        current_quota = response_resource(module, response, "Quota", "service quota")
    except is_boto3_error_code("NoSuchResourceException"):
        try:
            response = client.get_aws_default_service_quota(**quota_request, aws_retry=True)
            current_quota = response_resource(module, response, "Quota", "default service quota")
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to get AWS default service quota " f"{service_code}/{quota_code}"),
            )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS service quota {service_code}/{quota_code}",
        )

    validate_current_quota(module, current_quota, service_code, quota_code)

    pending_requests = []

    try:
        for status in ("CASE_OPENED", "PENDING"):
            response = paginated_query_with_retries(
                client,
                "list_requested_service_quota_change_history_by_quota",
                **dict(quota_request, Status=status),
            )
            requests = response_resources(module, response, "RequestedQuotas", "quota change history")
            for request in requests:
                validate_quota_request(module, request, service_code, quota_code, status=status)

            pending_requests.extend(requests)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=("Unable to list AWS service quota change history for " f"{service_code}/{quota_code}"),
        )

    current_quota_details = boto3_resource_to_ansible_dict(
        current_quota,
        transform_tags=False,
        force_tags=False,
    )
    current_value = current_quota_details["value"]

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
                response = client.request_service_quota_increase(
                    **dict(quota_request, DesiredValue=desired_value),
                    aws_retry=True,
                )
                requested_quota = response_resource(module, response, "RequestedQuota", "quota increase")
                validate_quota_request(
                    module,
                    requested_quota,
                    service_code,
                    quota_code,
                    desired_value=desired_value,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to request AWS service quota increase for " f"{quota_code} for service {service_code}"
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
