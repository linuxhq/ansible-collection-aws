#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sns_topic_attributes
version_added: '1.9.0'
short_description: Manage AWS Simple Notification Service topic attributes
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
attributes:
  check_mode:
    description: The module reports the attributes that would result from the requested changes.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - All attributes returned by C(GetTopicAttributes) are included, and
      attribute values are returned as strings as AWS returns them.
  returned: always
  type: dict
  contains:
    archive_policy:
      description: JSON message archive policy of a FIFO topic.
      returned: when returned by AWS
      type: str
    beginning_archive_time:
      description: Earliest time from which archived FIFO topic messages can be replayed.
      returned: when returned by AWS
      type: str
    content_based_deduplication:
      description: Whether content-based deduplication is enabled for a FIFO topic, as V(true) or V(false).
      returned: when returned by AWS
      type: str
    delivery_policy:
      description: JSON delivery policy of the topic.
      returned: when returned by AWS
      type: str
    display_name:
      description: Display name used in the C(From) field for email notifications.
      returned: when returned by AWS
      type: str
    effective_delivery_policy:
      description: JSON effective delivery policy, including system defaults.
      returned: when returned by AWS
      type: str
    fifo_topic:
      description: Whether the topic is a FIFO topic, as V(true) or V(false).
      returned: when returned by AWS
      type: str
    kms_master_key_id:
      description: AWS KMS key identifier used for topic encryption.
      returned: when returned by AWS
      type: str
    maximum_message_size:
      description: Maximum message size in bytes, returned only when explicitly set.
      returned: when returned by AWS
      type: str
    owner:
      description: AWS account ID of the topic owner.
      returned: when returned by AWS
      type: str
    policy:
      description: JSON access control policy of the topic.
      returned: when returned by AWS
      type: str
    signature_version:
      description: Signature version used to sign notifications.
      returned: when returned by AWS
      type: str
    subscriptions_confirmed:
      description: Number of confirmed subscriptions.
      returned: when returned by AWS
      type: str
    subscriptions_deleted:
      description: Number of deleted subscriptions.
      returned: when returned by AWS
      type: str
    subscriptions_pending:
      description: Number of subscriptions pending confirmation.
      returned: when returned by AWS
      type: str
    topic_arn:
      description: ARN of the topic.
      returned: when returned by AWS
      type: str
    tracing_config:
      description: Tracing mode of the topic, such as V(PassThrough) or V(Active).
      returned: when returned by AWS
      type: str
topic_arn:
  description: The ARN of the managed topic.
  returned: always
  type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)

MANAGED_ATTRIBUTES = ["kms_master_key_id"]


def main():
    argument_spec = {
        "kms_master_key_id": {"type": "str"},
        "topic_arn": {"required": True, "type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sns", retry_decorator=AWSRetry.jittered_backoff())

    methods = {"get_topic_attributes": ("TopicArn",)}
    if any(module.params[attribute] is not None for attribute in MANAGED_ATTRIBUTES):
        methods["set_topic_attributes"] = (
            "AttributeName",
            "AttributeValue",
            "TopicArn",
        )

    require_client_methods(module, client, "SNS", methods)

    topic_arn = module.params["topic_arn"]

    desired_parameters = {}
    for attribute in MANAGED_ATTRIBUTES:
        module_value = module.params[attribute]

        if module_value is None:
            continue

        desired_parameters[attribute] = module_value

    try:
        response = client.get_topic_attributes(
            TopicArn=topic_arn,
            aws_retry=True,
        )
    except is_boto3_error_code("NotFound"):
        module.fail_json(msg=f"AWS Simple Notification Service topic does not exist {topic_arn}")
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Simple Notification Service topic attributes for {topic_arn}",
        )

    if not isinstance(response, dict) or not isinstance(response.get("Attributes", {}), dict):
        module.fail_json(msg=f"Unexpected response while getting topic attributes for {topic_arn}")

    current_attributes = response.get("Attributes", {})

    desired_attributes = snake_dict_to_camel_dict(desired_parameters, capitalize_first=True)
    current_normalized = boto3_resource_to_ansible_dict(current_attributes, transform_tags=False, force_tags=False)
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
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=f"Unable to manage AWS Simple Notification Service topic attributes for {topic_arn}",
                    )

        current_attributes = dict(current_attributes)
        current_attributes.update(desired_attributes)

    result = {
        "attributes": boto3_resource_to_ansible_dict(current_attributes, transform_tags=False, force_tags=False),
        "changed": changed,
        "topic_arn": topic_arn,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
