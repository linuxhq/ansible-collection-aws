#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub
short_description: Manage aws notifications hubs
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

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def ensure_absent(client, module):
    hub = next(
        (
            item
            for item in paginated_query_with_retries(
                client, "list_notification_hubs"
            ).get("notificationHubs", [])
            if item.get("notificationHubRegion") == module.params["region"]
        ),
        None,
    )
    changed = hub is not None

    if changed and not module.check_mode:
        try:
            client.deregister_notification_hub(
                **scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {"notification_hub_region": module.params["region"]},
                        capitalize_first=False,
                    )
                ),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Notifications hub {module.params['region']}",
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    hub = next(
        (
            item
            for item in paginated_query_with_retries(
                client, "list_notification_hubs"
            ).get("notificationHubs", [])
            if item.get("notificationHubRegion") == module.params["region"]
        ),
        None,
    )
    desired_hub = {"notification_hub_region": module.params["region"]}
    changed = hub is None

    if changed and not module.check_mode:
        try:
            client.register_notification_hub(
                **scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {"notification_hub_region": module.params["region"]},
                        capitalize_first=False,
                    )
                ),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Notifications hub {module.params['region']}",
            )
        hub = desired_hub
    elif changed and module.check_mode:
        hub = desired_hub

    module.exit_json(
        changed=changed,
        notification_hub=boto3_resource_to_ansible_dict(
            hub, transform_tags=False, force_tags=False
        ),
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
    client = module.client(
        "notifications",
        region="us-east-1",
        retry_decorator=AWSRetry.jittered_backoff(),
    )

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
