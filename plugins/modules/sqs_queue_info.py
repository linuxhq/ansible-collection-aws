#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sqs_queue_info
version_added: '1.9.0'
short_description: Gather information about AWS Simple Queue Service queues
description:
  - Gathers information about AWS Simple Queue Service queues.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - SQS queue name used to limit the result set.
      - This must not be empty when provided.
      - A queue that does not exist results in an empty list.
      - Mutually exclusive with O(queue_name_prefix).
    type: str
  queue_name_prefix:
    description:
      - Optional queue name prefix used to filter the list of queues.
      - Mutually exclusive with O(name).
    type: str
  queue_owner_aws_account_id:
    description:
      - AWS account ID of the account that created the queue in O(name).
      - Requires O(name).
    type: str
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
- name: Gather information about an SQS queue
  linuxhq.aws.sqs_queue_info:
    name: molecule-bounce

- name: Gather information about all SQS queues
  linuxhq.aws.sqs_queue_info:

- name: Gather information about SQS queues using a name prefix
  linuxhq.aws.sqs_queue_info:
    queue_name_prefix: molecule-
"""

RETURN = r"""
queues:
  description:
    - A list of AWS Simple Queue Service queues.
    - Each queue includes C(name) and C(queue_url) added by the module, and
      C(tags) from C(ListQueueTags).
    - All attributes returned by C(GetQueueAttributes) are included with
      snake case names, and attribute values are returned as strings as AWS
      returns them.
  returned: always
  type: list
  elements: dict
  contains:
    approximate_number_of_messages:
      description: Approximate number of messages available for retrieval.
      returned: when returned by AWS
      type: str
    approximate_number_of_messages_delayed:
      description: Approximate number of delayed messages.
      returned: when returned by AWS
      type: str
    approximate_number_of_messages_not_visible:
      description: Approximate number of in-flight messages.
      returned: when returned by AWS
      type: str
    content_based_deduplication:
      description: Whether content-based deduplication is enabled for a FIFO queue, as V(true) or V(false).
      returned: when returned by AWS
      type: str
    created_timestamp:
      description: Queue creation time in seconds since the epoch.
      returned: when returned by AWS
      type: str
    deduplication_scope:
      description: Deduplication scope of a FIFO queue, V(messageGroup) or V(queue).
      returned: when returned by AWS
      type: str
    delay_seconds:
      description: Default delivery delay in seconds.
      returned: when returned by AWS
      type: str
    fifo_queue:
      description: Whether the queue is a FIFO queue, as V(true) or V(false).
      returned: when returned by AWS
      type: str
    fifo_throughput_limit:
      description: FIFO throughput quota scope, V(perQueue) or V(perMessageGroupId).
      returned: when returned by AWS
      type: str
    kms_data_key_reuse_period_seconds:
      description: Seconds a data key is reused before calling AWS KMS again.
      returned: when returned by AWS
      type: str
    kms_master_key_id:
      description: AWS KMS key identifier used for queue encryption.
      returned: when returned by AWS
      type: str
    last_modified_timestamp:
      description: Last queue attribute change time in seconds since the epoch.
      returned: when returned by AWS
      type: str
    maximum_message_size:
      description: Maximum message size in bytes.
      returned: when returned by AWS
      type: str
    message_retention_period:
      description: Message retention period in seconds.
      returned: when returned by AWS
      type: str
    name:
      description: Queue name.
      returned: always
      type: str
    policy:
      description: JSON access policy of the queue.
      returned: when returned by AWS
      type: str
    queue_arn:
      description: Queue ARN.
      returned: when returned by AWS
      type: str
    queue_url:
      description: Queue URL.
      returned: always
      type: str
    receive_message_wait_time_seconds:
      description: Long polling wait time in seconds.
      returned: when returned by AWS
      type: str
    redrive_allow_policy:
      description: JSON policy that controls which source queues can use this queue as a dead-letter queue.
      returned: when returned by AWS
      type: str
    redrive_policy:
      description: JSON dead-letter queue redrive policy.
      returned: when returned by AWS
      type: str
    sqs_managed_sse_enabled:
      description: Whether SQS-managed server-side encryption is enabled, as V(true) or V(false).
      returned: when returned by AWS
      type: str
    tags:
      description:
        - Queue tags.
        - Tag keys keep their original case.
      returned: always
      type: dict
    visibility_timeout:
      description: Visibility timeout in seconds.
      returned: when returned by AWS
      type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)

QUEUE_NOT_FOUND_CODES = (
    "AWS.SimpleQueueService.NonExistentQueue",
    "QueueDoesNotExist",
)


def get_queue(client, module, queue_url):
    try:
        response = client.get_queue_attributes(
            AttributeNames=["All"],
            QueueUrl=queue_url,
            aws_retry=True,
        )
    except is_boto3_error_code(QUEUE_NOT_FOUND_CODES):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS SQS queue {queue_url}")

    if not isinstance(response, dict) or not isinstance(response.get("Attributes", {}), dict):
        module.fail_json(msg=f"Unexpected response while getting AWS SQS queue {queue_url}")

    attributes = response.get("Attributes", {})

    try:
        response = client.list_queue_tags(QueueUrl=queue_url, aws_retry=True)
    except is_boto3_error_code(QUEUE_NOT_FOUND_CODES):
        return None
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to list AWS SQS queue tags for {queue_url}")

    if not isinstance(response, dict) or not isinstance(response.get("Tags", {}), dict):
        module.fail_json(msg=f"Unexpected response while listing AWS SQS queue tags for {queue_url}")

    queue = boto3_resource_to_ansible_dict(attributes, transform_tags=False, force_tags=False)
    queue["tags"] = response.get("Tags", {})

    queue_arn = queue.get("queue_arn")
    queue["name"] = (queue_arn or queue_url.rsplit("/", 1)[-1]).split(":")[-1]
    queue["queue_url"] = queue_url
    return queue


def main():
    argument_spec = {
        "name": {"type": "str"},
        "queue_name_prefix": {"type": "str"},
        "queue_owner_aws_account_id": {"type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["name", "queue_name_prefix"]],
        required_by={"queue_owner_aws_account_id": ["name"]},
        supports_check_mode=True,
    )
    name = module.params["name"]
    queue_name_prefix = module.params["queue_name_prefix"]
    queue_owner_aws_account_id = module.params["queue_owner_aws_account_id"]

    if name == "":
        module.fail_json(msg="name must not be empty")

    client = module.client("sqs", retry_decorator=AWSRetry.jittered_backoff())

    methods = {
        "get_queue_attributes": ("AttributeNames", "QueueUrl"),
        "list_queue_tags": ("QueueUrl",),
    }
    if name:
        methods["get_queue_url"] = ("QueueName",) + (("QueueOwnerAWSAccountId",) if queue_owner_aws_account_id else ())
    else:
        methods["list_queues"] = ("MaxResults",) + (("QueueNamePrefix",) if queue_name_prefix else ())

    require_client_methods(
        module,
        client,
        "SQS",
        methods,
    )

    if name:
        request = {"QueueName": name}
        if queue_owner_aws_account_id:
            request["QueueOwnerAWSAccountId"] = queue_owner_aws_account_id

        try:
            response = client.get_queue_url(
                **request,
                aws_retry=True,
            )
        except is_boto3_error_code(QUEUE_NOT_FOUND_CODES):
            queue_url = None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to get AWS SQS queue URL for {name}")
        else:
            queue_url = response.get("QueueUrl") if isinstance(response, dict) else None
            if not isinstance(queue_url, str) or not queue_url:
                module.fail_json(msg=f"Unexpected response while getting AWS SQS queue URL for {name}")

        queue = get_queue(client, module, queue_url) if queue_url else None
        queues = [queue] if queue is not None else []
    else:
        request = {"MaxResults": 1000}
        if queue_name_prefix:
            request["QueueNamePrefix"] = queue_name_prefix

        queue_urls = query_list(
            module,
            client,
            "list_queues",
            "QueueUrls",
            "Unable to list AWS SQS queues",
            **request,
        )

        queues = []
        for queue_url in queue_urls:
            queue = get_queue(client, module, queue_url)

            if queue is not None:
                queues.append(queue)

    module.exit_json(
        changed=False,
        queues=queues,
    )


if __name__ == "__main__":
    main()
