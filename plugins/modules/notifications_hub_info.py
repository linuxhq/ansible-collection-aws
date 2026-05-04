#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub_info
version_added: 1.9.1
short_description: Gather information about AWS Notifications hubs
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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_notification_hubs(client, module):
    hubs = []
    next_token = None

    while True:
        kwargs = {}
        if next_token:
            kwargs["nextToken"] = next_token

        try:
            response = client.list_notification_hubs(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Notifications hubs",
            )

        hubs.extend(response.get("notificationHubs", []))
        next_token = response.get("nextToken")
        if not next_token:
            break

    return hubs


def main():
    module = AnsibleAWSModule(
        argument_spec={},
        supports_check_mode=True,
    )
    client = module.client("notifications", region="us-east-1")

    module.exit_json(
        changed=False,
        notification_hubs=[
            camel_dict_to_snake_dict(notification_hub)
            for notification_hub in list_notification_hubs(client, module)
        ],
    )


if __name__ == "__main__":
    main()
