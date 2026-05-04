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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import (
    list_notification_hubs,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={},
        supports_check_mode=True,
    )
    client = module.client("notifications", region="us-east-1")

    module.exit_json(
        changed=False,
        notification_hubs=boto3_resource_list_to_ansible_dict(
            list_notification_hubs(client, module),
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
