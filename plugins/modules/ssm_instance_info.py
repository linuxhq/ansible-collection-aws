#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_instance_info
version_added: '1.9.0'
short_description: Gather information about AWS Systems Manager instances
description:
  - Gathers information about AWS Systems Manager managed instances.
  - This includes the Systems Manager ping status used to determine whether an
    instance is online for Session Manager.
author:
  - Taylor Kimball (@tkimball83)
options:
  connection_status:
    default: false
    description:
      - Whether to add the Session Manager connection status of each returned
        instance.
      - When V(true), the C(GetConnectionStatus) API is called once for each
        returned instance.
      - SSM Agent can report a C(ping_status) of C(Online) before the instance
        accepts Session Manager connections, so use this connection status to
        wait for a session to be accepted.
    type: bool
    version_added: '2.6.0'
  filters:
    description:
      - A dict of filters to apply when describing Systems Manager instances.
      - Filter names and values are passed to the SSM
        C(DescribeInstanceInformation) API.
      - Filter values must not be null.
    type: dict
  instance_ids:
    description:
      - EC2 instance IDs or managed instance IDs used to limit the result set.
      - This is added as an C(InstanceIds) Systems Manager instance filter and
        takes precedence over a C(InstanceIds) key in O(filters).
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

- name: Gather Session Manager connection status for selected instances
  linuxhq.aws.ssm_instance_info:
    connection_status: true
    instance_ids:
      - i-0123456789abcdef0

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
    - A list of matching Systems Manager managed instance IDs, in the order of C(instances).
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
      contains:
        detailed_status:
          description: Detailed association status.
          returned: when available
          type: str
        instance_association_status_aggregated_count:
          description:
            - Number of associations in each status.
            - Status names, such as C(Success) and C(Failed), are returned as
              AWS returns them.
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
    connection_status:
      description:
        - Whether the managed instance is ready to receive Session Manager
          connections.
        - Values, such as C(connected) and C(notconnected), are returned as AWS
          returns them.
      returned: when O(connection_status=true)
      type: str
      version_added: '2.6.0'
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
      description:
        - Whether the latest SSM Agent version is running on the managed
          instance.
        - AWS documents that this does not indicate whether the latest version
          is installed on Windows Server instances.
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
      type: str
    source_type:
      description: Source resource type for the managed instance.
      returned: when available
      type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    association_overview,
    require_non_null_ssm_filter_values,
    ssm_filter_list,
)


def get_connection_status(module, client, instance_id):
    try:
        response = client.get_connection_status(Target=instance_id, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS Systems Manager connection status for {instance_id}")

    return response["Status"]


def main():
    argument_spec = {
        "connection_status": {"default": False, "type": "bool"},
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
    connection_status = module.params["connection_status"]
    instance_ids = list(dict.fromkeys(module.params["instance_ids"] or []))
    ping_status = module.params["ping_status"]
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    request = {}
    filters = dict(module.params["filters"] or {})

    if instance_ids:
        filters["InstanceIds"] = instance_ids

    if ping_status:
        filters["PingStatus"] = ping_status

    if filters:
        require_non_null_ssm_filter_values(module, filters)
        request["Filters"] = ssm_filter_list(filters)

    methods = {"describe_instance_information": tuple(request)}
    if connection_status:
        methods["get_connection_status"] = ("Target",)

    require_client_methods(module, client, "Systems Manager", methods)

    instances = query_list(
        module,
        client,
        "describe_instance_information",
        "InstanceInformationList",
        "Unable to describe AWS Systems Manager instances",
        **request,
    )
    matching_instance_ids = [instance["InstanceId"] for instance in instances]

    results = boto3_resource_list_to_ansible_dict(
        instances,
        transform_tags=False,
        force_tags=False,
        nested_transforms={
            "AssociationOverview": lambda overview: association_overview(
                overview, "InstanceAssociationStatusAggregatedCount"
            )
        },
    )
    if connection_status:
        for instance_id, result in zip(matching_instance_ids, results):
            result["connection_status"] = get_connection_status(module, client, instance_id)

    module.exit_json(
        changed=False,
        instance_ids=matching_instance_ids,
        instances=results,
    )


if __name__ == "__main__":
    main()
