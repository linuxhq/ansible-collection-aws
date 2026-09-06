#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_instance_info
short_description: Gather information about AWS Systems Manager instances
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
      - Entries must not be empty.
      - This is added as an C(InstanceIds) Systems Manager instance filter and
        takes precedence over a C(InstanceIds) key in O(filters).
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
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - Records without a valid instance ID remain in C(instances) but are omitted
      from this list, so the two lists are not guaranteed to align by index.
  returned: always
  type: list
  elements: str
instances:
  description:
    - A list of Systems Manager managed instances.
  returned: always
  type: list
  elements: dict
  contains:
    activation_id:
      description: Activation ID used to register the managed instance.
      returned: when available
      type: str
    agent_version:
      description: Version of the SSM Agent running on the managed instance.
      returned: when available
      type: str
    association_overview:
      description: Summary of the managed instance's association states.
      returned: when available
      type: dict
    association_status:
      description: State of the most recent Systems Manager association.
      returned: when available
      type: str
    computer_name:
      description: Fully qualified host name of the managed instance.
      returned: when available
      type: str
    iam_role:
      description: IAM role assigned to the managed instance.
      returned: when available
      type: str
    instance_id:
      description: Managed instance ID.
      returned: when available
      type: str
    ip_address:
      description: IP address of the managed instance.
      returned: when available
      type: str
    is_latest_version:
      description: Whether the installed SSM Agent is the latest available version.
      returned: when available
      type: bool
    last_association_execution_date:
      description: Time when an association last ran on the managed instance.
      returned: when available
      type: str
    last_ping_date_time:
      description: Time when the SSM Agent last pinged Systems Manager.
      returned: when available
      type: str
    last_successful_association_execution_date:
      description: Time when an association last completed successfully.
      returned: when available
      type: str
    name:
      description: Name assigned to the managed instance.
      returned: when available
      type: str
    ping_status:
      description: Connection status of the managed instance.
      returned: when available
      type: str
    platform_name:
      description: Name of the operating system platform.
      returned: when available
      type: str
    platform_type:
      description: Type of operating system platform.
      returned: when available
      type: str
    platform_version:
      description: Version of the operating system platform.
      returned: when available
      type: str
    registration_date:
      description: Time when the managed instance was registered.
      returned: when available
      type: str
    resource_type:
      description: Type of managed resource.
      returned: when available
      type: str
    source_id:
      description: Source resource ID for the managed instance.
      returned: when available
      type: str
    source_location:
      description: Source location details for the managed instance.
      returned: when available
      type: list
      elements: dict
    source_type:
      description: Source resource type for the managed instance.
      returned: when available
      type: str
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
    instance_ids = list(dict.fromkeys(module.params["instance_ids"] or []))
    ping_status = module.params["ping_status"]

    if len(instance_ids) > 100:
        module.fail_json(msg="instance_ids must contain at most 100 instance IDs")

    if any(not instance_id for instance_id in instance_ids):
        module.fail_json(msg="instance_ids must not contain empty entries")

    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

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

            request["Filters"].append({"Key": key, "Values": [str(item) for item in values]})

    require_client_methods(
        module,
        client,
        "Systems Manager",
        {"describe_instance_information": tuple(request)},
    )

    instances = query_list(
        module,
        client,
        "describe_instance_information",
        "InstanceInformationList",
        "Unable to describe AWS Systems Manager instances",
        **request,
    )
    if not isinstance(instances, list):
        module.fail_json(
            msg="Unexpected response while describing AWS Systems Manager instances; instance list was not a list"
        )

    matching_instance_ids = []
    for index, instance in enumerate(instances):
        if not isinstance(instance, dict):
            module.fail_json(
                msg=(
                    "Unexpected response while describing AWS Systems Manager instances; "
                    f"instance {index} was not a dictionary"
                )
            )

        # Unlike modules that need an ID for follow-on API calls, this module
        # can preserve the complete record for compatibility. Do not expose an
        # invalid value in the convenience instance_ids list.
        instance_id = instance.get("InstanceId")
        if not isinstance(instance_id, str) or not instance_id:
            module.warn(
                "Unexpected response while describing AWS Systems Manager instances; "
                f"instance {index} did not contain a valid InstanceId and was omitted from instance_ids"
            )
            continue

        matching_instance_ids.append(instance_id)

    module.exit_json(
        changed=False,
        instance_ids=matching_instance_ids,
        instances=boto3_resource_list_to_ansible_dict(instances, transform_tags=False, force_tags=False),
    )


if __name__ == "__main__":
    main()
