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
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import (
    aws_notification_hub,
    get_notification_hub_by_region,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
)


def ensure_absent(client, module):
    hub = get_notification_hub_by_region(client, module, module.params["region"])
    changed = hub is not None

    if changed and not module.check_mode:
        aws_response(
            client,
            module,
            "deregister_notification_hub",
            error_message=f"Unable to delete AWS Notifications hub {module.params['region']}",
            **aws_notification_hub(module.params["region"]),
        )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    desired_hub = aws_notification_hub(module.params["region"])
    hub = get_notification_hub_by_region(client, module, module.params["region"])
    changed = hub is None

    if changed and not module.check_mode:
        aws_response(
            client,
            module,
            "register_notification_hub",
            error_message=f"Unable to create AWS Notifications hub {module.params['region']}",
            **desired_hub,
        )
        hub = desired_hub
    elif changed and module.check_mode:
        hub = desired_hub

    module.exit_json(
        changed=changed,
        notification_hub=aws_resource_to_snake_dict(hub),
        state="present",
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
