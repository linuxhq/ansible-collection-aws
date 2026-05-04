#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub
version_added: 1.9.1
short_description: Manage AWS Notifications hubs
description:
  - Manages AWS Notifications hubs.
author:
  - Taylor Kimball (@tkimball83)
options:
  region:
    description:
      - The notification hub region.
    required: true
    type: str
  state:
    description:
      - Whether the notification hub should exist.
    choices:
      - absent
      - present
    default: present
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure an AWS Notifications hub is present
  linuxhq.aws.notifications_hub:
    region: us-west-1

- name: Ensure an AWS Notifications hub is absent
  linuxhq.aws.notifications_hub:
    region: us-west-1
    state: absent
"""

RETURN = r"""
notification_hub:
  description:
    - The notification hub.
  returned: when a hub exists after module execution
  type: dict
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import (
    list_notification_hubs,
)


def get_notification_hub_by_region(client, module, region):
    for hub in list_notification_hubs(client, module):
        if hub.get("notificationHubRegion") == region:
            return hub
    return None


def ensure_present(client, module):
    hub = get_notification_hub_by_region(client, module, module.params["region"])
    changed = hub is None

    if changed and not module.check_mode:
        register_notification_hub = AWSRetry.jittered_backoff()(
            client.register_notification_hub
        )
        try:
            register_notification_hub(notificationHubRegion=module.params["region"])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Notifications hub {module.params['region']}",
            )
        hub = {
            "notificationHubRegion": module.params["region"],
        }
    elif changed and module.check_mode:
        hub = {
            "notificationHubRegion": module.params["region"],
        }

    module.exit_json(
        changed=changed,
        notification_hub=(
            boto3_resource_to_ansible_dict(hub, force_tags=False)
            if hub is not None
            else None
        ),
        state="present",
    )


def ensure_absent(client, module):
    hub = get_notification_hub_by_region(client, module, module.params["region"])
    changed = hub is not None

    if changed and not module.check_mode:
        deregister_notification_hub = AWSRetry.jittered_backoff()(
            client.deregister_notification_hub
        )
        try:
            deregister_notification_hub(notificationHubRegion=module.params["region"])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Notifications hub {module.params['region']}",
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "region": {"required": True, "type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    client = module.client("notifications", region="us-east-1")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
