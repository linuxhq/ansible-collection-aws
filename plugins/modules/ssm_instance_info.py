#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - This is added as an C(InstanceIds) Systems Manager instance filter and
        takes precedence over an C(InstanceIds) key in O(filters).
      - This must contain at most 100 instance IDs.
    elements: str
    type: list
  ping_status:
    choices:
      - ConnectionLost
      - Inactive
      - Online
    description:
      - Systems Manager ping status used to limit the result set.
      - This is added as a C(PingStatus) Systems Manager instance filter and
        takes precedence over a C(PingStatus) key in O(filters).
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


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
    instance_ids = module.params["instance_ids"]
    ping_status = module.params["ping_status"]

    if instance_ids and len(instance_ids) > 100:
        module.fail_json(msg="instance_ids must contain at most 100 instance IDs")

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "Systems Manager",
        {"describe_instance_information": ("Filters",)},
    )

    request = {}
    filters = dict(module.params["filters"] or {})

    if instance_ids:
        filters["InstanceIds"] = instance_ids
    if ping_status:
        filters["PingStatus"] = ping_status
    if filters:
        request["Filters"] = []
        for key, value in filters.items():
            values = value if isinstance(value, list) else [value]

            request["Filters"].append(
                {"Key": key, "Values": [str(item) for item in values]}
            )

    instances = query_list(
        module,
        client,
        "describe_instance_information",
        "InstanceInformationList",
        "Unable to describe AWS Systems Manager instances",
        **request
    )

    instances = boto3_resource_list_to_ansible_dict(
        instances, transform_tags=False, force_tags=False
    )

    matching_instance_ids = []
    for instance in instances:
        instance_id = instance.get("instance_id")

        if instance_id:
            matching_instance_ids.append(instance_id)

    module.exit_json(
        changed=False,
        instance_ids=matching_instance_ids,
        instances=instances,
    )


if __name__ == "__main__":
    main()
