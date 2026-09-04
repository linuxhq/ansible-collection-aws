#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub_info
short_description: Gather information about AWS Notifications hubs
description:
  - Gathers information about AWS Notifications hubs.
  - The module always uses the C(us-east-1) AWS Notifications endpoint.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: The module only retrieves information from AWS.
    support: full
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
  contains:
    creation_time:
      description: The date and time when the hub was created.
      returned: always
      type: str
    last_activation_time:
      description: The date and time when the hub was last activated.
      returned: when provided by AWS
      type: str
    notification_hub_region:
      description: The AWS Region of the notification hub.
      returned: always
      type: str
    status_summary:
      description: The hub status and its reason.
      returned: always
      type: dict
      contains:
        reason:
          description: The reason for the current status.
          returned: always
          type: str
        status:
          description: The current hub status.
          returned: always
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

HUB_STATUSES = ("ACTIVE", "DEREGISTERING", "INACTIVE", "REGISTERING")


def validate_hubs(module, hubs):
    if not isinstance(hubs, list):
        module.fail_json(msg="Unable to list AWS Notifications hubs: AWS returned an invalid response")

    for hub in hubs:
        if not isinstance(hub, dict):
            module.fail_json(msg="Unable to list AWS Notifications hubs: AWS returned an invalid hub")
        status_summary = hub.get("statusSummary")
        if (
            not isinstance(hub.get("notificationHubRegion"), str)
            or not hub["notificationHubRegion"]
            or hub.get("creationTime") is None
            or not isinstance(status_summary, dict)
            or status_summary.get("status") not in HUB_STATUSES
            or not isinstance(status_summary.get("reason"), str)
        ):
            module.fail_json(msg="Unable to list AWS Notifications hubs: AWS returned an invalid hub")
    return hubs


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

    require_client_methods(
        module,
        client,
        "Notifications",
        {"list_notification_hubs": ("maxResults", "nextToken")},
    )

    notification_hubs = query_list(
        module,
        client,
        "list_notification_hubs",
        "notificationHubs",
        "Unable to list AWS Notifications hubs",
    )
    validate_hubs(module, notification_hubs)

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
