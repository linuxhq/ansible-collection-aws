#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_topic_attributes
short_description: Manage aws simple notification service topics
description:
  - Manages selected AWS Simple Notification Service topic attributes.
  - Supports managing the topic KMS master key attribute.
author:
  - Taylor Kimball (@tkimball83)
options:
  kms_master_key_id:
    description:
      - The AWS KMS key identifier to use for topic encryption.
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
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

MANAGED_ATTRIBUTES = ["kms_master_key_id"]


def get_topic_attributes(client, module):
    try:
        return client.get_topic_attributes(
            TopicArn=module.params["topic_arn"],
            aws_retry=True,
        ).get("Attributes", {})
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to get AWS Simple Notification Service topic attributes "
                f"for {module.params['topic_arn']}"
            ),
        )


def main():
    argument_spec = {
        "kms_master_key_id": {"type": "str"},
        "topic_arn": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sns", retry_decorator=AWSRetry.jittered_backoff())

    current_attributes = get_topic_attributes(client, module)
    desired_parameters = {
        attribute: module.params[attribute]
        for attribute in MANAGED_ATTRIBUTES
        if module.params[attribute] is not None
    }
    desired_attributes = snake_dict_to_camel_dict(
        desired_parameters, capitalize_first=True
    )
    current = boto3_resource_to_ansible_dict(
        current_attributes, transform_tags=False, force_tags=False
    )
    current = {key: current.get(key) for key in desired_parameters}
    changed = current != desired_parameters

    if changed and not module.check_mode:
        for attribute, value in desired_attributes.items():
            try:
                client.set_topic_attributes(
                    AttributeName=attribute,
                    AttributeValue=value,
                    TopicArn=module.params["topic_arn"],
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to manage AWS Simple Notification Service topic "
                        f"attributes for {module.params['topic_arn']}"
                    ),
                )
        current_attributes = dict(current_attributes)
        current_attributes.update(desired_attributes)
    elif changed and module.check_mode:
        current_attributes = dict(current_attributes)
        current_attributes.update(desired_attributes)

    result = {
        "attributes": boto3_resource_to_ansible_dict(
            current_attributes, transform_tags=False, force_tags=False
        ),
        "changed": changed,
        "topic_arn": module.params["topic_arn"],
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
