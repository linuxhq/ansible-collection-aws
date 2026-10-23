#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_sms_attributes
version_added: '1.9.0'
short_description: Manage AWS Simple Notification Service SMS attributes
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
attributes:
  check_mode:
    description: The module reports the attributes that would result from the requested changes.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - An attribute cleared with an empty string is omitted, including in
      check mode.
  returned: always
  type: dict
  contains:
    default_sender_id:
      description: Default sender ID displayed on receiving devices.
      returned: when configured
      type: str
    default_sms_type:
      description: Default SMS message type.
      returned: when configured
      type: str
    delivery_status_iam_role:
      description: IAM role ARN used to write SMS delivery logs.
      returned: when configured
      type: str
    delivery_status_success_sampling_rate:
      description: Percentage of successful deliveries written to delivery logs.
      returned: when configured
      type: str
    monthly_spend_limit:
      description: Monthly SMS spending limit in USD.
      returned: when configured
      type: str
    usage_report_s3_bucket:
      description: S3 bucket receiving daily SMS usage reports.
      returned: when configured
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
from ansible_collections.linuxhq.aws.plugins.module_utils.sns import get_sms_attributes

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
        module.fail_json(msg="delivery_status_success_sampling_rate must be between 0 and 100")

    client = module.client(
        "sns",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["Throttled"]),
    )

    desired = {
        attribute_name: str(module.params[module_key])
        for module_key, attribute_name in MANAGED_ATTRIBUTES.items()
        if module.params[module_key] is not None
    }

    methods = {"get_sms_attributes": ()}
    if desired:
        methods["set_sms_attributes"] = ("attributes",)

    require_client_methods(
        module,
        client,
        "SNS",
        methods,
    )

    current_attributes = get_sms_attributes(client, module)

    # GetSMSAttributes omits unset attributes, so they compare as empty strings.
    current = {attribute_name: current_attributes.get(attribute_name) or "" for attribute_name in desired}

    changed = current != desired

    if changed and module.check_mode:
        current_attributes = dict(current_attributes, **desired)
        # SetSMSAttributes removes an attribute set to an empty string, so GetSMSAttributes omits it.
        for attribute_name, value in desired.items():
            if not value:
                current_attributes.pop(attribute_name)
    elif changed:
        try:
            client.set_sms_attributes(attributes=desired, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg="Unable to manage AWS Simple Notification Service SMS attributes",
            )

        current_attributes = get_sms_attributes(client, module, changed=True)

    module.exit_json(
        attributes=boto3_resource_to_ansible_dict(current_attributes, transform_tags=False, force_tags=False),
        changed=changed,
    )


if __name__ == "__main__":
    main()
