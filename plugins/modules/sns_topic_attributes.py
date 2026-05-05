#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_topic_attributes
version_added: 1.9.1
short_description: Manage AWS Simple Notification Service topic attributes
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
    validated_field_differences,
)

MANAGED_ATTRIBUTE_MAP = {
    "kms_master_key_id": "KmsMasterKeyId",
}


def get_topic_attributes(client, module):
    return aws_resource(
        client,
        module,
        "get_topic_attributes",
        "Attributes",
        default={},
        TopicArn=module.params["topic_arn"],
    )


def build_desired_attributes(module):
    return scrub_none_parameters(
        {
            attribute: module.params[parameter]
            for parameter, attribute in MANAGED_ATTRIBUTE_MAP.items()
        }
    )


def normalize_attributes(attributes):
    return aws_resource_to_snake_dict(attributes)


def main():
    argument_spec = {
        "kms_master_key_id": {"type": "str"},
        "topic_arn": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sns")

    current_attributes = get_topic_attributes(client, module)
    desired_attributes = build_desired_attributes(module)
    desired_normalized_attributes = normalize_attributes(desired_attributes)

    _, changed = validated_field_differences(
        module,
        current_attributes,
        desired_normalized_attributes,
        desired_normalized_attributes.keys(),
    )

    if changed and not module.check_mode:
        for attribute, value in desired_attributes.items():
            if current_attributes.get(attribute) == value:
                continue
            aws_response(
                client,
                module,
                "set_topic_attributes",
                error_message=(
                    "Unable to manage AWS Simple Notification Service topic "
                    f"attributes for {module.params['topic_arn']}"
                ),
                AttributeName=attribute,
                AttributeValue=value,
                TopicArn=module.params["topic_arn"],
            )
        current_attributes = get_topic_attributes(client, module)
    elif changed and module.check_mode:
        current_attributes = dict(current_attributes)
        current_attributes.update(desired_attributes)

    result = {
        "attributes": normalize_attributes(current_attributes),
        "changed": changed,
        "topic_arn": module.params["topic_arn"],
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
