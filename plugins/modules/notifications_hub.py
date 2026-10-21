#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_hub
version_added: '1.9.0'
short_description: Manage AWS Notifications hubs
description:
  - Manages AWS Notifications hubs.
  - The module always uses the C(us-east-1) AWS Notifications endpoint.
  - AWS does not allow deregistering the last C(ACTIVE) notification hub, so
    O(state=absent) fails without changes for that hub.
author:
  - Taylor Kimball (@tkimball83)
options:
  region:
    aliases:
      - aws_region
      - ec2_region
    description:
      - The notification hub region.
      - This selects the notification hub to manage, not the API endpoint.
      - A O(region) set through C(module_defaults) applies, as it does for other AWS modules.
      - The E(AWS_REGION) or E(AWS_DEFAULT_REGION) environment variable can also be used, in decreasing
        order of preference.
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
attributes:
  diff_mode:
    description: Diff mode is not supported.
    support: none
  check_mode:
    description: Predicts notification hub changes without modifying AWS.
    support: full
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
  contains:
    creation_time:
      description: The date and time when the hub was created.
      returned: when provided by AWS
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
      returned: when provided by AWS
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
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

import re

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.parameters import env_fallback

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)

# Registering a region while its hub is deregistering raises a modeled ConflictException.
REGISTER_RETRY = AWSRetry.jittered_backoff(catch_extra_error_codes=["ConflictException"])


def validate_hub(module, hub, operation, require_status=True, changed=False):
    if (
        not isinstance(hub, dict)
        or not isinstance(hub.get("notificationHubRegion"), str)
        or not hub["notificationHubRegion"]
    ):
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid hub")

    status_summary = hub.get("statusSummary")
    if (require_status or status_summary is not None) and (
        not isinstance(status_summary, dict)
        or not isinstance(status_summary.get("status"), str)
        or not status_summary["status"]
        or not isinstance(status_summary.get("reason"), str)
    ):
        module.fail_json(changed=changed, msg=f"{operation}: AWS returned an invalid hub")

    return hub


def list_notification_hubs(client, module):
    hubs = query_list(
        module,
        client,
        "list_notification_hubs",
        "notificationHubs",
        "Unable to list AWS Notifications hubs",
    )

    if not isinstance(hubs, list):
        module.fail_json(msg="Unable to list AWS Notifications hubs: AWS returned an invalid response")

    for hub in hubs:
        validate_hub(module, hub, "Unable to list AWS Notifications hubs")

    return hubs


def find_notification_hub(hubs, region):
    return next((hub for hub in hubs if hub["notificationHubRegion"] == region), None)


def hub_status(hub):
    return ((hub or {}).get("statusSummary") or {}).get("status")


def ensure_absent(client, module):
    region = module.params["region"]
    hubs = list_notification_hubs(client, module)
    hub = find_notification_hub(hubs, region)
    status = hub_status(hub)
    changed = hub is not None and status not in ("DEREGISTERING", "INACTIVE")

    if status == "ACTIVE" and not any(
        hub_status(other) == "ACTIVE" for other in hubs if other["notificationHubRegion"] != region
    ):
        module.fail_json(
            changed=False,
            msg=f"Unable to delete AWS Notifications hub {region}: AWS does not allow deregistering the last ACTIVE hub",
        )

    if changed and not module.check_mode:
        require_client_methods(
            module,
            client,
            "Notifications",
            {"deregister_notification_hub": ("notificationHubRegion",)},
        )
        try:
            client.deregister_notification_hub(
                notificationHubRegion=region,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            # The hub was deregistered after it was read, so this run changed nothing.
            changed = False
        except (BotoCoreError, ClientError) as e:
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
    hub = find_notification_hub(list_notification_hubs(client, module), region)
    status = hub_status(hub)
    changed = hub is None or status in ("DEREGISTERING", "INACTIVE")

    if changed and not module.check_mode:
        require_client_methods(
            module,
            client,
            "Notifications",
            {"register_notification_hub": ("notificationHubRegion",)},
        )
        try:
            hub = REGISTER_RETRY(client.register_notification_hub)(notificationHubRegion=region)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to create AWS Notifications hub {region}",
            )

        validate_hub(
            module, hub, f"Unable to create AWS Notifications hub {region}", require_status=False, changed=True
        )
        if hub["notificationHubRegion"] != region:
            module.fail_json(
                changed=True,
                msg=f"Unable to create AWS Notifications hub {region}: AWS returned a hub for a different region",
            )

        hub.pop("ResponseMetadata", None)
    elif changed and module.check_mode:
        hub = {"notificationHubRegion": region}

    module.exit_json(
        changed=changed,
        notification_hub=boto3_resource_to_ansible_dict(hub, transform_tags=False, force_tags=False),
        state="present",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "region": {
                "aliases": ["aws_region", "ec2_region"],
                "fallback": (env_fallback, ["AWS_REGION", "AWS_DEFAULT_REGION"]),
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
    region = module.params["region"]

    if not 2 <= len(region) <= 25 or not re.fullmatch(r"[a-z]{1,4}(?:-[a-z]{1,15})+-[0-9]", region):
        module.fail_json(msg="region must be a valid AWS region name")

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

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
