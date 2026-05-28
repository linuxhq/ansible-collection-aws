#!/usr/bin/python
# Copyright: Taylor Kimball
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
  names:
    description:
      - SQS queue names used to limit the result set.
    elements: str
    type: list
  queue_name_prefix:
    description:
      - Optional queue name prefix used to filter the list of queues.
    type: str
  queue_owner_aws_account_id:
    description:
      - AWS account ID of the account that created the queues in O(names).
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about an SQS queue
  linuxhq.aws.sqs_queue_info:
    names:
      - molecule-bounce

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
    try:
        attributes = client.get_queue_attributes(
            AttributeNames=["All"],
            QueueUrl=queue_url,
            aws_retry=True,
        ).get("Attributes", {})
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
        "names": {"elements": "str", "type": "list"},
        "queue_name_prefix": {"type": "str"},
        "queue_owner_aws_account_id": {"type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=[["names", "queue_name_prefix"]],
        supports_check_mode=True,
    )
    client = module.client("sqs", retry_decorator=AWSRetry.jittered_backoff())

    if module.params["names"]:
        queues = []
        for name in module.params["names"]:
            try:
                get_url_params = {"QueueName": name}
                if module.params["queue_owner_aws_account_id"] is not None:
                    get_url_params["QueueOwnerAWSAccountId"] = module.params[
                        "queue_owner_aws_account_id"
                    ]
                queue_url = client.get_queue_url(
                    **get_url_params,
                    aws_retry=True,
                ).get("QueueUrl")
            except is_boto3_error_code("AWS.SimpleQueueService.NonExistentQueue"):
                queue_url = None
            except Exception as e:
                module.fail_json_aws(e, msg="Unable to get AWS SQS queue URL")
            if queue_url:
                queues.append(get_queue(client, module, queue_url))
    else:
        request = {}
        if module.params["queue_name_prefix"] is not None:
            request["QueueNamePrefix"] = module.params["queue_name_prefix"]
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
            queues.append(get_queue(client, module, queue_url))

    module.exit_json(
        changed=False,
        queues=queues,
    )


if __name__ == "__main__":
    main()
