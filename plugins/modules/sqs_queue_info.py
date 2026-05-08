#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: sqs_queue_info
version_added: "1.9.5"
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

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def get_queue(client, module, queue_url):
    attributes = client.get_queue_attributes(
        **scrub_none_parameters(
            snake_dict_to_camel_dict(
                {
                    "attribute_names": ["All"],
                    "queue_url": queue_url,
                },
                capitalize_first=True,
            )
        ),
        aws_retry=True,
    ).get("Attributes", {})
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
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sqs", retry_decorator=AWSRetry.jittered_backoff())

    if module.params["name"]:
        try:
            queue_url = client.get_queue_url(
                **scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {"queue_name": module.params["name"]},
                        capitalize_first=True,
                    )
                ),
                aws_retry=True,
            ).get("QueueUrl")
        except is_boto3_error_code("AWS.SimpleQueueService.NonExistentQueue"):
            queue_url = None
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to get AWS SQS queue URL")
        queues = [get_queue(client, module, queue_url)] if queue_url else []
    else:
        queues = [
            get_queue(client, module, queue_url)
            for queue_url in paginated_query_with_retries(
                client,
                "list_queues",
            ).get("QueueUrls", [])
        ]

    module.exit_json(
        changed=False,
        queues=queues,
    )


if __name__ == "__main__":
    main()
