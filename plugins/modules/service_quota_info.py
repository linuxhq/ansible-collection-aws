#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota_info
short_description: Gather information about aws service quotas
description:
  - Gathers information about an AWS service quota.
  - Falls back to the AWS default quota when the quota has no applied value
    and no O(context_id) is provided.
author:
  - Taylor Kimball
options:
  context_id:
    description:
      - The context ID for a resource-level quota.
      - A resource-level quota that does not exist results in an empty
        RV(quota).
      - This option requires AWS SDK support for the C(ContextId) request
        parameter.
    type: str
  quota_code:
    description:
      - The quota code to gather.
    required: true
    type: str
  service_code:
    description:
      - The service code that owns the quota.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about an EC2 service quota
  linuxhq.aws.service_quota_info:
    quota_code: L-0263D0A3
    service_code: ec2

- name: Gather information about an IAM service quota in a specific region
  linuxhq.aws.service_quota_info:
    quota_code: L-0DA4ABF3
    region: us-east-1
    service_code: iam

- name: Gather information about a resource-level service quota
  linuxhq.aws.service_quota_info:
    context_id: arn:aws:example:us-east-1:123456789012:resource/example
    quota_code: L-0263D0A3
    service_code: ec2
"""

RETURN = r"""
quota:
  description:
    - The AWS service quota details.
  returned: always
  type: dict
quota_code:
  description: The gathered quota code.
  returned: always
  type: str
service_code:
  description: The gathered service code.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def main():
    argument_spec = {
        "context_id": {"type": "str"},
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client(
        "service-quotas", retry_decorator=AWSRetry.jittered_backoff()
    )
    context_id = module.params["context_id"]
    quota_code = module.params["quota_code"]
    service_code = module.params["service_code"]

    method_names = {"get_service_quota"}
    if not context_id:
        method_names.add("get_aws_default_service_quota")

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
    }
    if context_id:
        required_method_parameters["get_service_quota"].add("ContextId")

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

    request = {
        "QuotaCode": quota_code,
        "ServiceCode": service_code,
    }
    if context_id:
        request["ContextId"] = context_id

    try:
        quota = client.get_service_quota(**request, aws_retry=True).get("Quota", {})
    except is_boto3_error_code("NoSuchResourceException"):
        quota = {}
        if not context_id:
            try:
                quota = client.get_aws_default_service_quota(
                    **request, aws_retry=True
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

    module.exit_json(
        changed=False,
        quota=boto3_resource_to_ansible_dict(
            quota, transform_tags=False, force_tags=False
        ),
        quota_code=quota_code,
        service_code=service_code,
    )


if __name__ == "__main__":
    main()
