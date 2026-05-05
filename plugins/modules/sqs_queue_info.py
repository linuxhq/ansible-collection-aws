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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_resource,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
)


def get_queue(client, module, queue_url):
    attributes = aws_resource(
        client,
        module,
        "get_queue_attributes",
        "Attributes",
        default={},
        AttributeNames=["All"],
        QueueUrl=queue_url,
    )
    queue = aws_resource_to_snake_dict(attributes)
    queue["name"] = attributes.get("QueueArn", queue_url.rsplit("/", 1)[-1]).split(":")[
        -1
    ]
    queue["queue_url"] = queue_url
    return queue


def get_queue_url(client, module, queue_name):
    return aws_resource(
        client,
        module,
        "get_queue_url",
        "QueueUrl",
        ignore_error_codes="AWS.SimpleQueueService.NonExistentQueue",
        ignored_error_result=None,
        QueueName=queue_name,
    )


def list_queue_urls(client, module):
    return aws_paginated_list(
        client,
        module,
        "list_queues",
        "QueueUrls",
    )


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
