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
proposed_attributes:
  description:
    - The topic attributes that would be applied.
  returned: when changed
  type: dict
topic_arn:
  description: The ARN of the managed topic.
  returned: always
  type: str
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule

MANAGED_ATTRIBUTE_MAP = {
    "kms_master_key_id": "KmsMasterKeyId",
}


def get_topic_attributes(client, module):
    try:
        response = client.get_topic_attributes(TopicArn=module.params["topic_arn"])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Simple Notification Service topic attributes for {module.params['topic_arn']}",
        )

    return response.get("Attributes", {})


def build_proposed_attributes(module):
    proposed = {}
    for parameter, attribute in MANAGED_ATTRIBUTE_MAP.items():
        if module.params[parameter] is not None:
            proposed[attribute] = module.params[parameter]
    return proposed


def normalize_attributes(attributes):
    return camel_dict_to_snake_dict(attributes)


def main():
    argument_spec = {
        "kms_master_key_id": {"type": "str"},
        "topic_arn": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sns")

    current_attributes = get_topic_attributes(client, module)
    proposed_attributes = build_proposed_attributes(module)

    changed = False
    for attribute, value in proposed_attributes.items():
        if current_attributes.get(attribute) != value:
            changed = True
            break

    if changed and not module.check_mode:
        for attribute, value in proposed_attributes.items():
            if current_attributes.get(attribute) == value:
                continue
            try:
                client.set_topic_attributes(
                    AttributeName=attribute,
                    AttributeValue=value,
                    TopicArn=module.params["topic_arn"],
                )
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to manage AWS Simple Notification Service topic attributes for {module.params['topic_arn']}",
                )
        current_attributes = get_topic_attributes(client, module)
    elif changed and module.check_mode:
        current_attributes = dict(current_attributes)
        current_attributes.update(proposed_attributes)

    result = {
        "attributes": normalize_attributes(current_attributes),
        "changed": changed,
        "topic_arn": module.params["topic_arn"],
    }

    if changed:
        result["proposed_attributes"] = normalize_attributes(proposed_attributes)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
