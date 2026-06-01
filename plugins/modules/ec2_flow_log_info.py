#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_flow_log_info
short_description: Gather information about aws ec2 flow logs
description:
  - Gathers information about EC2 flow logs.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when describing EC2 flow logs.
      - Filter names and values are passed to the EC2 C(DescribeFlowLogs) API.
    type: dict
  flow_log_ids:
    description:
      - EC2 flow log IDs used to limit the result set.
    elements: str
    type: list
  resource_ids:
    description:
      - Resource IDs used to limit the result set.
      - This is added as a C(resource-id) EC2 flow log filter.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about all EC2 flow logs
  linuxhq.aws.ec2_flow_log_info:

- name: Gather information about selected EC2 flow logs
  linuxhq.aws.ec2_flow_log_info:
    flow_log_ids:
      - fl-0123456789abcdef0

- name: Gather information about flow logs for a VPC
  linuxhq.aws.ec2_flow_log_info:
    resource_ids:
      - vpc-0123456789abcdef0

- name: Gather information about active accepted-traffic flow logs
  linuxhq.aws.ec2_flow_log_info:
    filters:
      flow-log-status: ACTIVE
      traffic-type: ACCEPT
"""

RETURN = r"""
flow_logs:
  description:
    - A list of EC2 flow logs.
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


def main():
    argument_spec = {
        "filters": {"type": "dict"},
        "flow_log_ids": {"elements": "str", "type": "list"},
        "resource_ids": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    request = {}
    if module.params["flow_log_ids"]:
        request["FlowLogIds"] = module.params["flow_log_ids"]
    filters = dict(module.params["filters"] or {})

    if module.params["resource_ids"]:
        filters["resource-id"] = module.params["resource_ids"]
    if filters:
        request["Filter"] = ansible_dict_to_boto3_filter_list(filters)

    try:
        flow_logs = paginated_query_with_retries(
            client,
            "describe_flow_logs",
            **request,
        ).get("FlowLogs", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 flow logs")

    module.exit_json(
        changed=False,
        flow_logs=boto3_resource_list_to_ansible_dict(
            flow_logs, transform_tags=True, force_tags=False
        ),
    )


if __name__ == "__main__":
    main()
