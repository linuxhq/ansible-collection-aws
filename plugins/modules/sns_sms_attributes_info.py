#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_sms_attributes_info
short_description: Gather information about AWS Simple Notification Service SMS attributes
description:
  - Gathers information about AWS Simple Notification Service SMS attributes.
  - This module maps to the SNS C(GetSMSAttributes) API.
author:
  - Taylor Kimball (@tkimball83)
options:
  attributes:
    description:
      - A list of SMS attribute names for which values should be returned.
      - Attribute names use the SNS API format, for example
        C(DefaultSMSType).
      - If not supplied, all SMS attributes are returned.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about SNS SMS attributes
  linuxhq.aws.sns_sms_attributes_info:

- name: Gather information about selected SNS SMS attributes
  linuxhq.aws.sns_sms_attributes_info:
    attributes:
      - DefaultSMSType
      - MonthlySpendLimit
"""

RETURN = r"""
attributes:
  description:
    - The AWS Simple Notification Service SMS attributes.
    - Attribute names are returned in snake case, for example
      C(default_sms_type).
  returned: always
  type: dict
  contains:
    default_sender_id:
      description: Default sender ID displayed on receiving devices.
      returned: when configured and requested
      type: str
    default_sms_type:
      description: Default SMS message type.
      returned: when configured and requested
      type: str
    delivery_status_iam_role:
      description: IAM role ARN used to write SMS delivery logs.
      returned: when configured and requested
      type: str
    delivery_status_success_sampling_rate:
      description: Percentage of successful deliveries written to delivery logs.
      returned: when configured and requested
      type: str
    monthly_spend_limit:
      description: Monthly SMS spending limit in USD.
      returned: when configured and requested
      type: str
    usage_report_s3_bucket:
      description: S3 bucket receiving daily SMS usage reports.
      returned: when configured and requested
      type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def main():
    argument_spec = {
        "attributes": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sns", retry_decorator=AWSRetry.jittered_backoff())

    attributes = list(dict.fromkeys(module.params["attributes"] or []))
    request = {}
    if attributes:
        request["attributes"] = attributes

    require_client_methods(
        module,
        client,
        "SNS",
        {"get_sms_attributes": tuple(request)},
    )

    try:
        response = client.get_sms_attributes(**request, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Unable to get AWS Simple Notification Service SMS attributes")

    if not isinstance(response, dict) or not isinstance(response.get("attributes", {}), dict):
        module.fail_json(msg="Unexpected response while getting AWS Simple Notification Service SMS attributes")

    module.exit_json(
        attributes=boto3_resource_to_ansible_dict(
            response.get("attributes", {}), transform_tags=False, force_tags=False
        ),
        changed=False,
    )


if __name__ == "__main__":
    main()
