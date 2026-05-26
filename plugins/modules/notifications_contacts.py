#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts
short_description: Manage aws notifications contacts
description:
  - Manages AWS Notifications email contacts.
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
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  state:
    description:
      - Whether the notifications contact should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the notifications contact.
    type: dict
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
    tags:
      Name: molecule-dummy01

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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import compare_aws_tags
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def contact_with_tags(client, module, contact):
    if not contact or not contact.get("arn"):
        return contact
    contact = dict(contact)
    try:
        contact["tags"] = client.list_tags_for_resource(
            arn=contact["arn"],
            aws_retry=True,
        ).get("tags", {})
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Notifications contact {contact['arn']}",
        )
    return contact


def apply_tag_changes(client, module, contact, tags_to_set, tag_keys_to_unset):
    if tag_keys_to_unset:
        try:
            client.untag_resource(
                arn=contact["arn"],
                tagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from AWS Notifications contact {contact['arn']}",
            )

    if tags_to_set:
        try:
            client.tag_resource(
                arn=contact["arn"],
                tags=tags_to_set,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag AWS Notifications contact {contact['arn']}",
            )


def contact_with_updated_tags(contact, tags_to_set, tag_keys_to_unset):
    contact = dict(contact)
    tags = dict(contact.get("tags", {}))
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)
    tags.update(tags_to_set)
    contact["tags"] = tags
    return contact


def ensure_absent(client, module):
    contact = next(
        (
            item
            for item in paginated_query_with_retries(client, "list_email_contacts").get(
                "emailContacts", []
            )
            if item.get("address") == module.params["email_address"]
        ),
        None,
    )
    changed = contact is not None

    if changed and not module.check_mode:
        try:
            client.delete_email_contact(
                arn=contact["arn"],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to delete AWS Notifications contact "
                    f"{module.params['email_address']}"
                ),
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    contact = next(
        (
            item
            for item in paginated_query_with_retries(client, "list_email_contacts").get(
                "emailContacts", []
            )
            if item.get("address") == module.params["email_address"]
        ),
        None,
    )
    contact = contact_with_tags(client, module, contact)
    current_contact = (
        {"address": contact.get("address"), "name": contact.get("name")}
        if contact
        else None
    )
    desired_contact = {
        "address": module.params["email_address"],
        "name": module.params["name"],
    }
    resource_changed = (current_contact or {}) != desired_contact
    tags_to_set, tag_keys_to_unset = ({}, [])
    if module.params["tags"] is not None:
        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            (contact or {}).get("tags", {}),
            module.params["tags"],
            purge_tags=module.params["purge_tags"],
        )
    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if contact is None or resource_changed:
            if contact is not None:
                try:
                    client.delete_email_contact(
                        arn=contact["arn"],
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to delete AWS Notifications contact "
                            f"{module.params['email_address']}"
                        ),
                    )

            try:
                request = {
                    "emailAddress": module.params["email_address"],
                    "name": module.params["name"],
                }
                if module.params["tags"] is not None:
                    request["tags"] = module.params["tags"]
                contact_arn = client.create_email_contact(
                    **request, aws_retry=True
                ).get("arn")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        "Unable to create AWS Notifications contact "
                        f"{module.params['email_address']}"
                    ),
                )

            contact = dict(desired_contact, arn=contact_arn)
            if module.params["tags"] is not None:
                contact["tags"] = module.params["tags"]
        elif contact is not None:
            apply_tag_changes(client, module, contact, tags_to_set, tag_keys_to_unset)
            contact = contact_with_updated_tags(contact, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode:
        contact = desired_contact
        if module.params["tags"] is not None:
            contact["tags"] = module.params["tags"]

    module.exit_json(
        changed=changed,
        email_contact=boto3_resource_to_ansible_dict(
            contact, transform_tags=False, force_tags=False
        ),
        state="present",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "email_address": {"required": True, "type": "str"},
            "name": {"required": True, "type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "tags": {"type": "dict"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "notificationscontacts", retry_decorator=AWSRetry.jittered_backoff()
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
