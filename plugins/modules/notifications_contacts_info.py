#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts_info
version_added: 1.9.1
short_description: Gather information about AWS Notifications contacts
description:
  - Gathers information about AWS Notifications email contacts.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The notifications contact name to query.
      - When omitted, all notifications contacts are returned.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about AWS Notifications contacts
  linuxhq.aws.notifications_contacts_info:

- name: Gather information about a single AWS Notifications contact
  linuxhq.aws.notifications_contacts_info:
    name: molecule-dummy01
"""

RETURN = r"""
email_contacts:
  description:
    - The notifications contacts.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import (
    list_email_contacts,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("notificationscontacts")
    email_contacts = boto3_resource_list_to_ansible_dict(
        list_email_contacts(client, module),
        force_tags=False,
    )

    if module.params["name"] is not None:
        email_contacts = [
            contact
            for contact in email_contacts
            if contact.get("name") == module.params["name"]
        ]

    module.exit_json(
        changed=False,
        email_contacts=email_contacts,
    )


if __name__ == "__main__":
    main()
