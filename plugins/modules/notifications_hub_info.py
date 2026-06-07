#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub_info
short_description: Gather information about aws notifications hubs
description:
  - Gathers information about AWS Notifications hubs.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about AWS Notifications hubs
  linuxhq.aws.notifications_hub_info:
"""

RETURN = r"""
notification_hubs:
  description:
    - The notifications hubs.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={},
        supports_check_mode=True,
    )
    client = module.client(
        "notifications",
        region="us-east-1",
        retry_decorator=AWSRetry.jittered_backoff(),
    )

    try:
        get_boto3_client_method_parameters(client, "list_notification_hubs")
    except Exception:
        module.fail_json(
            msg="Installed botocore does not support AWS Notifications ListNotificationHubs"
        )

    try:
        notification_hubs = paginated_query_with_retries(
            client, "list_notification_hubs"
        ).get("notificationHubs", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Notifications hubs")

    module.exit_json(
        changed=False,
        notification_hubs=boto3_resource_list_to_ansible_dict(
            notification_hubs,
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
