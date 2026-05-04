#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sqs_queue_info
version_added: 1.9.1
short_description: Gather information about AWS Simple Queue Service queues
description:
  - Gathers information about AWS Simple Queue Service queues.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The AWS Simple Queue Service queue name to gather.
      - When omitted, all queues in the region are returned.
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
"""

RETURN = r"""
queues:
  description:
    - A list of AWS Simple Queue Service queues.
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


def get_queue(client, module, queue_url):
    get_queue_attributes = AWSRetry.jittered_backoff()(client.get_queue_attributes)
    try:
        response = get_queue_attributes(
            AttributeNames=["All"],
            QueueUrl=queue_url,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Simple Queue Service queue attributes for {queue_url}",
        )

    attributes = response.get("Attributes", {})
    queue = boto3_resource_to_ansible_dict(attributes, force_tags=False)
    queue["name"] = attributes.get("QueueArn", queue_url.rsplit("/", 1)[-1]).split(":")[
        -1
    ]
    queue["queue_url"] = queue_url
    return queue


def get_queue_url(client, module, queue_name):
    get_queue_url = AWSRetry.jittered_backoff()(client.get_queue_url)
    try:
        response = get_queue_url(QueueName=queue_name)
    except is_boto3_error_code("AWS.SimpleQueueService.NonExistentQueue"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Simple Queue Service queue URL for {queue_name}",
        )

    return response.get("QueueUrl")


def list_queue_urls(client, module):
    try:
        response = paginated_query_with_retries(client, "list_queues")
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to list AWS Simple Queue Service queue URLs"
        )

    return response.get("QueueUrls", [])


def main():
    argument_spec = {
        "name": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sqs")

    if module.params["name"]:
        queue_url = get_queue_url(client, module, module.params["name"])
        queues = [get_queue(client, module, queue_url)] if queue_url else []
    else:
        queues = [
            get_queue(client, module, queue_url)
            for queue_url in list_queue_urls(client, module)
        ]

    module.exit_json(
        changed=False,
        queues=queues,
    )


if __name__ == "__main__":
    main()
