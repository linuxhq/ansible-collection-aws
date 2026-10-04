#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota
version_added: '1.9.0'
short_description: Manage AWS service quotas
description:
  - Requests AWS service quota increases.
  - Only submits a quota increase request when the desired value is greater than the current applied quota
    and there is no existing open or pending request for the same quota.
  - Falls back to the AWS default quota when the quota has no applied value
    and no O(context_id) is provided.
  - Fails before requesting an increase for a quota that is not adjustable.
  - Warns when an open or pending request asks for less than O(value).
author:
  - Taylor Kimball (@tkimball83)
options:
  context_id:
    description:
      - The context ID for a resource-level quota.
      - This option requires AWS SDK support for the C(ContextId) request
        parameter.
    type: str
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

- name: Request a resource-level quota increase
  linuxhq.aws.service_quota:
    context_id: arn:aws:example:us-east-1:123456789012:resource/example
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
    - CloudWatch metric dimension names retain their original casing.
  returned: always
  type: dict
  contains:
    value:
      description: The current quota value.
      returned: always
      type: float
    adjustable:
      description: Whether the quota can be increased.
      returned: when returned by AWS
      type: bool
    description:
      description: The quota description.
      returned: when returned by AWS
      type: str
    error_reason:
      description: The reason the quota value could not be retrieved.
      returned: when returned by AWS
      type: dict
    global_quota:
      description: Whether the quota is global.
      returned: when returned by AWS
      type: bool
    period:
      description: The period over which the quota is measured.
      returned: when returned by AWS
      type: dict
    quota_applied_at_level:
      description: Whether the quota applies to the account or to resources.
      returned: when returned by AWS
      type: str
    quota_arn:
      description: The quota ARN.
      returned: when returned by AWS
      type: str
    quota_code:
      description: The quota code.
      returned: when returned by AWS
      type: str
    quota_context:
      description: The resource-level context of the quota.
      returned: when returned by AWS
      type: dict
    quota_name:
      description: The quota name.
      returned: when returned by AWS
      type: str
    service_code:
      description: The service code.
      returned: when returned by AWS
      type: str
    service_name:
      description: The service name.
      returned: when returned by AWS
      type: str
    unit:
      description: The quota unit.
      returned: when returned by AWS
      type: str
    usage_metric:
      description: The CloudWatch metric that tracks usage of the quota.
      returned: when returned by AWS
      type: dict
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
    case_id:
      description: The support case ID.
      returned: when returned by AWS
      type: str
    created:
      description: The date and time the request was created.
      returned: when returned by AWS
      type: str
    global_quota:
      description: Whether the quota is global.
      returned: when returned by AWS
      type: bool
    id:
      description: The request ID.
      returned: when returned by AWS
      type: str
    last_updated:
      description: The date and time the request was last updated.
      returned: when returned by AWS
      type: str
    quota_arn:
      description: The quota ARN.
      returned: when returned by AWS
      type: str
    quota_code:
      description: The quota code.
      returned: when returned by AWS
      type: str
    quota_context:
      description: The resource-level context of the request.
      returned: when returned by AWS
      type: dict
    quota_name:
      description: The quota name.
      returned: when returned by AWS
      type: str
    quota_requested_at_level:
      description: Whether the request applies to the account or to a resource.
      returned: when returned by AWS
      type: str
    request_type:
      description: The type of quota increase request.
      returned: when returned by AWS
      type: str
    requester:
      description: The IAM identity that made the request.
      returned: when returned by AWS
      type: str
    service_code:
      description: The service code.
      returned: when returned by AWS
      type: str
    service_name:
      description: The service name.
      returned: when returned by AWS
      type: str
    unit:
      description: The quota unit.
      returned: when returned by AWS
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
    status:
      description: The request status.
      returned: always
      type: str
    case_id:
      description: The support case ID.
      returned: when returned by AWS
      type: str
    created:
      description: The date and time the request was created.
      returned: when returned by AWS
      type: str
    global_quota:
      description: Whether the quota is global.
      returned: when returned by AWS
      type: bool
    id:
      description: The request ID.
      returned: when returned by AWS
      type: str
    last_updated:
      description: The date and time the request was last updated.
      returned: when returned by AWS
      type: str
    quota_arn:
      description: The quota ARN.
      returned: when returned by AWS
      type: str
    quota_code:
      description: The quota code.
      returned: when returned by AWS
      type: str
    quota_context:
      description: The resource-level context of the request.
      returned: when returned by AWS
      type: dict
    quota_name:
      description: The quota name.
      returned: when returned by AWS
      type: str
    quota_requested_at_level:
      description: Whether the request applies to the account or to a resource.
      returned: when returned by AWS
      type: str
    request_type:
      description: The type of quota increase request.
      returned: when returned by AWS
      type: str
    requester:
      description: The IAM identity that made the request.
      returned: when returned by AWS
      type: str
    service_code:
      description: The service code.
      returned: when returned by AWS
      type: str
    service_name:
      description: The service name.
      returned: when returned by AWS
      type: str
    unit:
      description: The quota unit.
      returned: when returned by AWS
      type: str
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
from ansible_collections.linuxhq.aws.plugins.module_utils.service_quotas import (
    get_quota,
    quota_to_ansible_dict,
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
        "context_id": {"type": "str"},
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
        "value": {"required": True, "type": "float"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)

    if not math.isfinite(module.params["value"]) or not 0 <= module.params["value"] <= 10000000000:
        module.fail_json(msg="value must be between 0 and 10000000000")

    client = module.client("service-quotas", retry_decorator=AWSRetry.jittered_backoff())

    context_id = module.params.get("context_id") or None
    quota_code = module.params["quota_code"]
    service_code = module.params["service_code"]
    desired_value = module.params["value"]
    identifier = f"{service_code}/{quota_code}" + (f" for {context_id}" if context_id else "")
    quota_request = {
        "QuotaCode": quota_code,
        "ServiceCode": service_code,
    }
    if context_id:
        quota_request["ContextId"] = context_id

    history_request = {
        "QuotaCode": quota_code,
        "ServiceCode": service_code,
    }
    if context_id:
        history_request["QuotaRequestedAtLevel"] = "RESOURCE"

    methods = {
        "get_service_quota": tuple(quota_request),
        "list_requested_service_quota_change_history_by_quota": (
            ("MaxResults", "NextToken", "Status") + tuple(history_request)
        ),
    }
    if not context_id:
        methods["get_aws_default_service_quota"] = ("QuotaCode", "ServiceCode")

    if not module.check_mode:
        methods["request_service_quota_increase"] = ("DesiredValue",) + tuple(quota_request)

    require_client_methods(module, client, "Service Quotas", methods)

    current_quota = get_quota(client, module, service_code, quota_code, context_id)
    if current_quota is None:
        module.fail_json(msg=f"AWS service quota {identifier} does not exist")

    validate_current_quota(module, current_quota, service_code, quota_code)

    pending_requests = []

    try:
        for status in ("CASE_OPENED", "PENDING"):
            response = paginated_query_with_retries(
                client,
                "list_requested_service_quota_change_history_by_quota",
                **dict(history_request, Status=status),
            )
            requests = response_resources(module, response, "RequestedQuotas", "quota change history")
            for request in requests:
                validate_quota_request(module, request, service_code, quota_code, status=status)

            if context_id:
                # Resource-level history covers every resource, so keep only this context.
                requests = [
                    request
                    for request in requests
                    if (request.get("QuotaContext") or {}).get("ContextId") == context_id
                ]

            pending_requests.extend(requests)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to list AWS service quota change history for {identifier}")

    current_quota_details = quota_to_ansible_dict(current_quota)
    current_value = current_quota_details["value"]

    has_pending_request = bool(pending_requests)
    changed = not has_pending_request and desired_value > current_value

    if changed and current_quota.get("Adjustable") is False:
        module.fail_json(
            msg=f"AWS service quota {identifier} is not adjustable, so it cannot be increased to {desired_value}"
        )

    smaller_requests = [
        request["DesiredValue"]
        for request in pending_requests
        if isinstance(request.get("DesiredValue"), (int, float)) and request["DesiredValue"] < desired_value
    ]
    if desired_value > current_value and smaller_requests:
        module.warn(
            f"AWS service quota {identifier} has an open request for {max(smaller_requests)}, "
            f"so an increase to {desired_value} can be requested only after it is resolved"
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
                        "quota_code": quota_code,
                        "quota_context": {"context_id": context_id} if context_id else None,
                        "quota_name": current_quota_details.get("quota_name"),
                        "quota_requested_at_level": "RESOURCE" if context_id else "ACCOUNT",
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
                module.fail_json_aws(e, msg=f"Unable to request AWS service quota increase for {identifier}")

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
