#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub
short_description: Manage aws notifications hubs
description:
  - Manages AWS Notifications hubs.
  - The module always uses the C(us-east-1) AWS Notifications endpoint.
author:
  - Taylor Kimball (@tkimball83)
options:
  region:
    description:
      - The notification hub region.
      - This must match the AWS region name format, for example V(us-west-2).
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_notification_hub(client, module):
    region = module.params["region"]

    try:
        hubs = paginated_query_with_retries(client, "list_notification_hubs").get(
            "notificationHubs", []
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Notifications hubs")

    for hub in hubs:
        if hub.get("notificationHubRegion") == region:
            return hub
    return None


def ensure_absent(client, module):
    region = module.params["region"]
    hub = get_notification_hub(client, module)
    changed = hub is not None

    if changed and not module.check_mode:
        try:
            client.deregister_notification_hub(
                notificationHubRegion=region,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS Notifications hub {region}",
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    region = module.params["region"]
    hub = get_notification_hub(client, module)
    changed = hub is None

    if changed and not module.check_mode:
        try:
            hub = client.register_notification_hub(
                notificationHubRegion=region,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Notifications hub {region}",
            )

        hub.pop("ResponseMetadata", None)
    elif changed and module.check_mode:
        hub = {"notification_hub_region": region}

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
            "region": {
                "aliases": ["aws_region", "ec2_region"],
                "required": True,
                "type": "str",
            },
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    state = module.params["state"]

    client = module.client(
        "notifications",
        region="us-east-1",
        retry_decorator=AWSRetry.jittered_backoff(),
    )
    methods = {"list_notification_hubs": ("maxResults", "nextToken")}
    if state == "present":
        methods["register_notification_hub"] = ("notificationHubRegion",)
    if state == "absent":
        methods["deregister_notification_hub"] = ("notificationHubRegion",)

    require_client_methods(module, client, "Notifications", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
