#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: service_quota_info
version_added: '1.9.0'
short_description: Gather information about AWS service quotas
description:
  - Gathers information about an AWS service quota.
  - Falls back to the AWS default quota when the quota has no applied value.
  - Returns an empty RV(quota) when the quota has neither an applied value
    nor an AWS default value.
author:
  - Taylor Kimball (@tkimball83)
options:
  context_id:
    description:
      - The context ID for a resource-level quota.
      - When the resource has no applied value of its own, RV(quota) is the
        quota that applies to every resource in the scope, or the AWS default
        quota, so its C(quota_context.context_id) is C(*) or absent.
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
attributes:
  check_mode:
    description: This module does not modify AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - CloudWatch metric dimension names retain their original casing.
  returned: always
  type: dict
  contains:
    value:
      description: The quota value.
      returned: when the quota has an applied or AWS default value
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
      description:
        - The resource-level context of the quota.
        - The C(context_id) is C(*) for the value that applies to every
          resource in the scope.
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
quota_code:
  description: The gathered quota code.
  returned: always
  type: str
service_code:
  description: The gathered service code.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.service_quotas import (
    get_quota,
    quota_to_ansible_dict,
)


def main():
    argument_spec = {
        "context_id": {"type": "str"},
        "quota_code": {"required": True, "type": "str"},
        "service_code": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("service-quotas", retry_decorator=AWSRetry.jittered_backoff())
    context_id = module.params["context_id"] or None
    quota_code = module.params["quota_code"]
    service_code = module.params["service_code"]

    methods = {
        "get_aws_default_service_quota": ("QuotaCode", "ServiceCode"),
        "get_service_quota": ("QuotaCode", "ServiceCode"),
    }
    if context_id:
        methods["get_service_quota"] += ("ContextId",)

    require_client_methods(module, client, "Service Quotas", methods)

    quota = get_quota(client, module, service_code, quota_code, context_id) or {}

    module.exit_json(
        changed=False,
        quota=quota_to_ansible_dict(quota),
        quota_code=quota_code,
        service_code=service_code,
    )


if __name__ == "__main__":
    main()
