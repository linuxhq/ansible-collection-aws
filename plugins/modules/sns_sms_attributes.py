#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_sms_attributes
short_description: Manage aws simple notification service sms attributes
description:
  - Manages AWS Simple Notification Service SMS attributes.
  - This module maps to the SNS C(SetSMSAttributes) API.
  - Without any attribute options the module only reports the current
    attributes.
author:
  - Taylor Kimball (@tkimball83)
options:
  default_sender_id:
    description:
      - The default sender ID displayed as the sender on receiving devices.
    type: str
  default_sms_type:
    choices:
      - Promotional
      - Transactional
    description:
      - The default SMS message type.
    type: str
  delivery_status_iam_role:
    description:
      - The ARN of the IAM role that allows SNS to write SMS delivery logs to
        CloudWatch Logs.
    type: str
  delivery_status_success_sampling_rate:
    description:
      - The percentage of successful SMS deliveries for which SNS writes logs
        to CloudWatch Logs.
      - The value must be an integer from C(0) to C(100).
    type: int
  monthly_spend_limit:
    description:
      - The maximum amount in USD to spend each month for SMS messages.
    type: str
  usage_report_s3_bucket:
    description:
      - The S3 bucket name where SNS delivers daily SMS usage reports.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure SNS SMS attributes are configured
  linuxhq.aws.sns_sms_attributes:
    default_sms_type: Transactional
    monthly_spend_limit: "25"

- name: Ensure SNS SMS delivery logging is configured
  linuxhq.aws.sns_sms_attributes:
    delivery_status_iam_role: arn:aws:iam::123456789012:role/example-sns-sms
    delivery_status_success_sampling_rate: 10
"""

RETURN = r"""
attributes:
  description:
    - The current AWS Simple Notification Service SMS attributes after module
      execution.
    - Attribute names are returned in snake case, for example
      C(default_sms_type).
  returned: always
  type: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

MANAGED_ATTRIBUTES = {
    "default_sender_id": "DefaultSenderID",
    "default_sms_type": "DefaultSMSType",
    "delivery_status_iam_role": "DeliveryStatusIAMRole",
    "delivery_status_success_sampling_rate": "DeliveryStatusSuccessSamplingRate",
    "monthly_spend_limit": "MonthlySpendLimit",
    "usage_report_s3_bucket": "UsageReportS3Bucket",
}


def main():
    argument_spec = {
        "default_sender_id": {"type": "str"},
        "default_sms_type": {
            "choices": ["Promotional", "Transactional"],
            "type": "str",
        },
        "delivery_status_iam_role": {"type": "str"},
        "delivery_status_success_sampling_rate": {"type": "int"},
        "monthly_spend_limit": {"type": "str"},
        "usage_report_s3_bucket": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)

    sampling_rate = module.params["delivery_status_success_sampling_rate"]

    if sampling_rate is not None and not 0 <= sampling_rate <= 100:
        module.fail_json(
            msg="delivery_status_success_sampling_rate must be between 0 and 100"
        )

    client = module.client("sns", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SNS",
        {
            "get_sms_attributes": (),
            "set_sms_attributes": ("attributes",),
        },
    )

    desired = {}
    for module_key, attribute_name in MANAGED_ATTRIBUTES.items():
        module_value = module.params[module_key]

        if module_value is None:
            continue

        desired[attribute_name] = str(module_value)

    try:
        current_attributes = client.get_sms_attributes(aws_retry=True).get(
            "attributes", {}
        )
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to get AWS Simple Notification Service SMS attributes"
        )

    current = {}
    for attribute_name in desired:
        current[attribute_name] = current_attributes.get(attribute_name)

    changed = current != desired

    if changed:
        if not module.check_mode:
            try:
                client.set_sms_attributes(attributes=desired, aws_retry=True)
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg="Unable to manage AWS Simple Notification Service SMS attributes",
                )

        current_attributes = dict(current_attributes)
        current_attributes.update(desired)

    module.exit_json(
        attributes=boto3_resource_to_ansible_dict(
            current_attributes, transform_tags=False, force_tags=False
        ),
        changed=changed,
    )


if __name__ == "__main__":
    main()
