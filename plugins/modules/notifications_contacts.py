#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts
version_added: 1.9.1
short_description: Manage AWS Notifications contacts
description:
  - Manages AWS Notifications email contacts.
  - O(name) is immutable after contact creation.
author:
  - Taylor Kimball (@tkimball83)
options:
  email_address:
    description:
      - The email address for the notifications contact.
    required: true
    type: str
  name:
    description:
      - The notifications contact name.
    required: true
    type: str
  state:
    description:
      - Whether the notifications contact should exist.
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
- name: Ensure an AWS Notifications contact is present
  linuxhq.aws.notifications_contacts:
    email_address: dummy01@molecule.org
    name: molecule-dummy01

- name: Ensure an AWS Notifications contact is absent
  linuxhq.aws.notifications_contacts:
    email_address: dummy01@molecule.org
    name: molecule-dummy01
    state: absent
"""

RETURN = r"""
email_contact:
  description:
    - The notifications contact.
  returned: when a contact exists after module execution
  type: dict
state:
  description:
    - The requested state.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_resource,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    validate_immutable_fields,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.notifications import (
    get_email_contact_by_address,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
)


def ensure_absent(client, module):
    contact = get_email_contact_by_address(
        client, module, module.params["email_address"]
    )
    changed = contact is not None

    if changed and not module.check_mode:
        aws_response(
            client,
            module,
            "delete_email_contact",
            error_message=(
                "Unable to delete AWS Notifications contact "
                f"{module.params['email_address']}"
            ),
            arn=contact.get("arn"),
        )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    contact = get_email_contact_by_address(
        client, module, module.params["email_address"]
    )
    validate_immutable_fields(
        module,
        contact,
        {"name": module.params["name"]},
        ["name"],
        (
            "Unable to update AWS Notifications contact "
            f"{module.params['email_address']}: immutable fields differ"
        ),
    )

    changed = contact is None

    if changed and not module.check_mode:
        contact_arn = aws_resource(
            client,
            module,
            "create_email_contact",
            "arn",
            error_message=(
                "Unable to create AWS Notifications contact "
                f"{module.params['email_address']}"
            ),
            emailAddress=module.params["email_address"],
            name=module.params["name"],
        )

        contact = {
            "address": module.params["email_address"],
            "arn": contact_arn,
            "name": module.params["name"],
        }
    elif changed and module.check_mode:
        contact = {
            "address": module.params["email_address"],
            "name": module.params["name"],
        }

    module.exit_json(
        changed=changed,
        email_contact=aws_resource_to_snake_dict(contact),
        state="present",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "email_address": {"required": True, "type": "str"},
            "name": {"required": True, "type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    client = module.client("notificationscontacts")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
