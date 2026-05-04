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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") == (
        "AWS.SimpleQueueService.NonExistentQueue"
    )


def get_queue_url(client, module):
    try:
        response = client.get_queue_url(QueueName=module.params["name"])
    except Exception as e:
        if is_not_found_error(e):
            return None
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Simple Queue Service queue URL for {module.params['name']}",
        )

    return response.get("QueueUrl")


def list_queue_urls(client, module):
    queue_urls = []
    next_token = None

    try:
        while True:
            request = {}
            if next_token:
                request["NextToken"] = next_token

            response = client.list_queues(**request)
            queue_urls.extend(response.get("QueueUrls", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to list AWS Simple Queue Service queue URLs"
        )

    return queue_urls


def get_queue(queue_url, client, module):
    try:
        response = client.get_queue_attributes(
            AttributeNames=["All"],
            QueueUrl=queue_url,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Simple Queue Service queue attributes for {queue_url}",
        )

    attributes = response.get("Attributes", {})
    queue = camel_dict_to_snake_dict(attributes)
    queue["name"] = attributes.get("QueueArn", queue_url.rsplit("/", 1)[-1]).split(":")[
        -1
    ]
    queue["queue_url"] = queue_url
    return queue


def main():
    argument_spec = {
        "name": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sqs")

    if module.params["name"]:
        queue_url = get_queue_url(client, module)
        queues = [get_queue(queue_url, client, module)] if queue_url else []
    else:
        queues = [
            get_queue(queue_url, client, module)
            for queue_url in list_queue_urls(client, module)
        ]

    module.exit_json(
        changed=False,
        queues=queues,
    )


if __name__ == "__main__":
    main()
