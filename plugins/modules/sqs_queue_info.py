#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sqs_queue_info
short_description: Gather information about aws simple queue service queues
description:
  - Gathers information about AWS Simple Queue Service queues.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - SQS queue name used to limit the result set.
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
    - Each queue includes C(name) and C(queue_url) added by the module.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def get_queue(client, module, queue_url):
    try:
        attributes = client.get_queue_attributes(
            AttributeNames=["All"],
            QueueUrl=queue_url,
            aws_retry=True,
        ).get("Attributes", {})
    except is_boto3_error_code("AWS.SimpleQueueService.NonExistentQueue"):
        return None
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS SQS queue {queue_url}")

    queue = boto3_resource_to_ansible_dict(
        attributes, transform_tags=False, force_tags=False
    )

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
    client = module.client("sqs", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SQS",
        {
            "get_queue_url": ("QueueName", "QueueOwnerAWSAccountId"),
            "get_queue_attributes": ("AttributeNames", "QueueUrl"),
            "list_queues": ("QueueNamePrefix",),
        },
    )

    name = module.params["name"]
    queue_name_prefix = module.params["queue_name_prefix"]
    queue_owner_aws_account_id = module.params["queue_owner_aws_account_id"]

    if name:
        request = {"QueueName": name}
        if queue_owner_aws_account_id:
            request["QueueOwnerAWSAccountId"] = queue_owner_aws_account_id

        try:
            queue_url = client.get_queue_url(
                **request,
                aws_retry=True,
            ).get("QueueUrl")
        except is_boto3_error_code("AWS.SimpleQueueService.NonExistentQueue"):
            queue_url = None
        except Exception as e:
            module.fail_json_aws(e, msg=f"Unable to get AWS SQS queue URL for {name}")

        queue = get_queue(client, module, queue_url) if queue_url else None
        queues = [queue] if queue is not None else []
    else:
        request = {}
        if queue_name_prefix:
            request["QueueNamePrefix"] = queue_name_prefix

        try:
            queue_urls = paginated_query_with_retries(
                client,
                "list_queues",
                **request,
            ).get("QueueUrls", [])
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to list AWS SQS queues")

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
