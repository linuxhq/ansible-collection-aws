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

import re

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
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

    if state == "present":
        hub_region = module.params["region"]

        if not 2 <= len(hub_region) <= 25 or not re.fullmatch(
            r"([a-z]{1,2})-([a-z]{1,15}-)+([0-9])", hub_region
        ):
            module.fail_json(
                msg=(
                    "region must match the AWS region name format, "
                    "for example us-west-2"
                )
            )

    client = module.client(
        "notifications",
        region="us-east-1",
        retry_decorator=AWSRetry.jittered_backoff(),
    )
    method_names = {"list_notification_hubs"}
    if state == "present":
        method_names.add("register_notification_hub")
    elif state == "absent":
        method_names.add("deregister_notification_hub")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support Notifications {method_name}"
            )

    required_method_parameters = {
        "deregister_notification_hub": {"notificationHubRegion"},
        "list_notification_hubs": {"maxResults", "nextToken"},
        "register_notification_hub": {"notificationHubRegion"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support Notifications "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
