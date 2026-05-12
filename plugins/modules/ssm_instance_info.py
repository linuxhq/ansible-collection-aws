#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_instance_info
short_description: Gather information about aws systems manager instances
description:
  - Gathers information about AWS Systems Manager managed instances.
  - This includes the Systems Manager ping status used to determine whether an
    instance is online for Session Manager.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing Systems Manager instances.
      - Filter names and values are passed to the SSM
        C(DescribeInstanceInformation) API.
    type: dict
  instance_ids:
    description:
      - EC2 instance IDs or managed instance IDs used to limit the result set.
      - This is added as an C(InstanceIds) Systems Manager instance filter.
    elements: str
    type: list
  ping_status:
    choices:
      - ConnectionLost
      - Inactive
      - Online
    description:
      - Systems Manager ping status used to limit the result set.
      - This is added as a C(PingStatus) Systems Manager instance filter.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about all Systems Manager managed instances
  linuxhq.aws.ssm_instance_info:

- name: Gather information about selected Systems Manager managed instances
  linuxhq.aws.ssm_instance_info:
    instance_ids:
      - i-0123456789abcdef0

- name: Gather information about online Systems Manager managed instances
  linuxhq.aws.ssm_instance_info:
    ping_status: Online

- name: Gather information using Systems Manager filters
  linuxhq.aws.ssm_instance_info:
    filters:
      PlatformTypes:
        - Linux
      PingStatus:
        - Online
"""

RETURN = r"""
instance_ids:
  description:
    - A list of matching Systems Manager managed instance IDs.
  returned: always
  type: list
  elements: str
instances:
  description:
    - A list of Systems Manager managed instances.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
)


def normalized_filters(module):
    filters = dict(module.params["filters"] or {})
    if module.params["instance_ids"]:
        filters["InstanceIds"] = module.params["instance_ids"]
    if module.params["ping_status"]:
        filters["PingStatus"] = module.params["ping_status"]
    return filters


def ssm_filter_list(filters):
    return [
        {"Key": item["Name"], "Values": item["Values"]}
        for item in ansible_dict_to_boto3_filter_list(filters)
    ]


def build_request(module):
    filters = normalized_filters(module)
    if not filters:
        return {}
    return {"Filters": ssm_filter_list(filters)}


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "instance_ids": {"elements": "str", "type": "list"},
        "ping_status": {
            "choices": ["ConnectionLost", "Inactive", "Online"],
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    try:
        instances = paginated_query_with_retries(
            client,
            "describe_instance_information",
            **build_request(module),
        ).get("InstanceInformationList", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe AWS Systems Manager instances")

    instances = boto3_resource_list_to_ansible_dict(
        instances, transform_tags=False, force_tags=False
    )
    module.exit_json(
        changed=False,
        instance_ids=[
            instance["instance_id"]
            for instance in instances
            if instance.get("instance_id")
        ],
        instances=instances,
    )


if __name__ == "__main__":
    main()
