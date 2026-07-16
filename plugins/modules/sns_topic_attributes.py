#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_topic_attributes
short_description: Manage aws simple notification service topics
description:
  - Manages selected AWS Simple Notification Service topic attributes.
  - Supports managing the topic KMS master key attribute.
  - Without any attribute options the module only reports the current
    attributes.
author:
  - Taylor Kimball (@tkimball83)
options:
  kms_master_key_id:
    description:
      - The AWS KMS key identifier to use for topic encryption.
      - Set to an empty string V("") to disable server-side encryption.
    type: str
  topic_arn:
    description:
      - The ARN of the AWS Simple Notification Service topic.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure SNS topic encryption is configured
  linuxhq.aws.sns_topic_attributes:
    kms_master_key_id: alias/aws/sns
    topic_arn: arn:aws:sns:us-east-1:123456789012:example
"""

RETURN = r"""
attributes:
  description:
    - The current AWS Simple Notification Service topic attributes after module execution.
    - Attribute names are returned in snake case, for example
      C(kms_master_key_id).
  returned: always
  type: dict
topic_arn:
  description: The ARN of the managed topic.
  returned: always
  type: str
"""

from ansible.module_utils.common.dict_transformations import (
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

MANAGED_ATTRIBUTES = ["kms_master_key_id"]


def main():
    argument_spec = {
        "kms_master_key_id": {"type": "str"},
        "topic_arn": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sns", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SNS",
        {
            "get_topic_attributes": ("TopicArn",),
            "set_topic_attributes": ("AttributeName", "AttributeValue", "TopicArn"),
        },
    )

    topic_arn = module.params["topic_arn"]

    desired_parameters = {}
    for attribute in MANAGED_ATTRIBUTES:
        module_value = module.params[attribute]

        if module_value is None:
            continue

        desired_parameters[attribute] = module_value

    try:
        current_attributes = client.get_topic_attributes(
            TopicArn=topic_arn,
            aws_retry=True,
        ).get("Attributes", {})
    except is_boto3_error_code("NotFound"):
        if not module.check_mode:
            module.fail_json(
                msg=(
                    "AWS Simple Notification Service topic does not exist "
                    f"{topic_arn}"
                )
            )

        current_attributes = {}
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to get AWS Simple Notification Service topic attributes "
                f"for {topic_arn}"
            ),
        )

    desired_attributes = snake_dict_to_camel_dict(
        desired_parameters, capitalize_first=True
    )
    current_normalized = boto3_resource_to_ansible_dict(
        current_attributes, transform_tags=False, force_tags=False
    )
    current = {}
    for attribute in desired_parameters:
        current[attribute] = current_normalized.get(attribute) or ""

    changed = current != desired_parameters

    if changed:
        if not module.check_mode:
            for attribute, value in desired_attributes.items():
                try:
                    client.set_topic_attributes(
                        AttributeName=attribute,
                        AttributeValue=value,
                        TopicArn=topic_arn,
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to manage AWS Simple Notification Service topic "
                            f"attributes for {topic_arn}"
                        ),
                    )

        current_attributes = dict(current_attributes)
        current_attributes.update(desired_attributes)

    result = {
        "attributes": boto3_resource_to_ansible_dict(
            current_attributes, transform_tags=False, force_tags=False
        ),
        "changed": changed,
        "topic_arn": topic_arn,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
