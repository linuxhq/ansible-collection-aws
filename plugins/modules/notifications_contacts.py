#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts
short_description: Manage AWS Notifications contacts
description:
  - Manages AWS Notifications email contacts.
author:
  - Taylor Kimball (@tkimball83)
options:
  email_address:
    description:
      - The email address for the notifications contact.
      - This must be a valid email address of 6 to 254 characters.
    required: true
    type: str
  name:
    description:
      - The notifications contact name.
      - This must be 1 to 64 characters and contain at least one letter,
        digit, or one of C(_), C(-), C(.), or C(~).
      - Changing the name of an existing contact deletes and recreates the
        contact, and the new contact must be activated by email again.
      - This is required when O(state=present).
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
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts contact and tag changes without modifying AWS.
    support: full
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
    state: absent
"""

RETURN = r"""
email_contact:
  description:
    - The notifications contact.
  returned: when a contact exists after module execution
  type: dict
  contains:
    address:
      description: The contact email address.
      returned: always
      type: str
    arn:
      description: The contact ARN.
      returned: except when check mode predicts contact creation
      type: str
    creation_time:
      description: The date and time when the contact was created.
      returned: when provided by AWS
      type: str
    name:
      description: The contact name.
      returned: always
      type: str
    status:
      description: The contact activation status.
      returned: when provided by AWS
      type: str
    tags:
      description: The contact tags.
      returned: when O(tags) is provided
      type: dict
    update_time:
      description: The date and time when the contact was last updated.
      returned: when provided by AWS
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import compare_aws_tags
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tags


def apply_tag_deltas(contact, tags_to_set, tag_keys_to_unset):
    updated = dict(contact)
    updated_tags = dict(updated.get("tags", {}))

    for tag_key in tag_keys_to_unset:
        updated_tags.pop(tag_key, None)
    updated_tags.update(tags_to_set)
    updated["tags"] = updated_tags
    return updated


def validate_contact(module, contact, operation):
    if not isinstance(contact, dict) or not all(
        isinstance(contact.get(key), str) and contact[key] for key in ("address", "arn", "name")
    ):
        module.fail_json(msg=f"{operation}: AWS returned an invalid contact")
    return contact


def get_contact_by_address(client, module):
    email_address = module.params["email_address"]

    contacts = query_list(
        module,
        client,
        "list_email_contacts",
        "emailContacts",
        "Unable to list AWS Notifications contacts",
    )

    if not isinstance(contacts, list):
        module.fail_json(msg="Unable to list AWS Notifications contacts: AWS returned an invalid response")

    for contact in contacts:
        validate_contact(module, contact, "Unable to list AWS Notifications contacts")
        if contact.get("address") == email_address:
            return contact
    return None


def ensure_absent(client, module):
    contact = get_contact_by_address(client, module)
    changed = contact is not None

    if changed and not module.check_mode:
        require_client_methods(
            module,
            client,
            "NotificationsContacts",
            {"delete_email_contact": ("arn",)},
        )
        try:
            client.delete_email_contact(
                arn=contact["arn"],
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            pass
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to delete AWS Notifications contact " f"{module.params['email_address']}"),
            )

    module.exit_json(
        changed=changed,
        state="absent",
    )


def ensure_present(client, module):
    email_address = module.params["email_address"]
    name = module.params["name"]
    tags = module.params["tags"]
    contact = get_contact_by_address(client, module)
    current_contact = {"address": contact.get("address"), "name": contact.get("name")} if contact else None
    desired_contact = {
        "address": email_address,
        "name": name,
    }
    resource_changed = (current_contact or {}) != desired_contact

    tags_to_set, tag_keys_to_unset = ({}, [])
    needs_current_tags = contact is not None and (
        (tags is not None and not resource_changed) or (tags is None and resource_changed)
    )
    if needs_current_tags:
        contact = dict(contact)

        require_client_methods(
            module,
            client,
            "NotificationsContacts",
            {"list_tags_for_resource": ("arn",)},
        )
        try:
            tag_response = client.list_tags_for_resource(
                arn=contact["arn"],
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to list tags for AWS Notifications contact " f"{contact['arn']}"),
            )

        if (
            not isinstance(tag_response, dict)
            or not isinstance(tag_response.get("tags", {}), dict)
            or not all(
                isinstance(tag_key, str) and isinstance(tag_value, str)
                for tag_key, tag_value in tag_response.get("tags", {}).items()
            )
        ):
            module.fail_json(
                msg=(
                    f"Unable to list tags for AWS Notifications contact {contact['arn']}: AWS returned an invalid response"
                )
            )
        contact["tags"] = tag_response.get("tags", {})

        if not resource_changed:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                contact["tags"],
                tags,
                purge_tags=module.params["purge_tags"],
            )

    desired_tags = tags if tags is not None else contact.get("tags") if contact else None
    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if resource_changed:
            if contact is not None:
                require_client_methods(
                    module,
                    client,
                    "NotificationsContacts",
                    {"delete_email_contact": ("arn",)},
                )
                try:
                    client.delete_email_contact(
                        arn=contact["arn"],
                        aws_retry=True,
                    )
                except is_boto3_error_code("ResourceNotFoundException"):
                    pass
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=("Unable to delete AWS Notifications contact " f"{email_address}"),
                    )

            request = {
                "emailAddress": email_address,
                "name": name,
            }
            if desired_tags:
                request["tags"] = desired_tags

            require_client_methods(
                module,
                client,
                "NotificationsContacts",
                {"create_email_contact": tuple(request)},
            )
            try:
                create_response = client.create_email_contact(**request, aws_retry=True)
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS Notifications contact {email_address}",
                )

            if (
                not isinstance(create_response, dict)
                or not isinstance(create_response.get("arn"), str)
                or not create_response["arn"]
            ):
                module.fail_json(
                    msg=(
                        f"Unable to create AWS Notifications contact {email_address}: AWS returned an invalid response"
                    )
                )
            contact_arn = create_response["arn"]

            contact = None
            require_client_methods(
                module,
                client,
                "NotificationsContacts",
                {"get_email_contact": ("arn",)},
            )
            try:
                get_response = client.get_email_contact(
                    arn=contact_arn,
                    aws_retry=True,
                )
            except is_boto3_error_code("ResourceNotFoundException"):
                get_response = {"emailContact": None}
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to get AWS Notifications contact {contact_arn}",
                )

            if not isinstance(get_response, dict) or "emailContact" not in get_response:
                module.fail_json(
                    msg=f"Unable to get AWS Notifications contact {contact_arn}: AWS returned an invalid response"
                )
            contact = get_response.get("emailContact")

            if contact is None:
                contact = dict(desired_contact, arn=contact_arn)
            else:
                validate_contact(module, contact, f"Unable to get AWS Notifications contact {contact_arn}")
            if desired_tags is not None:
                contact["tags"] = desired_tags
        else:
            contact_arn = contact["arn"]
            if tag_keys_to_unset:
                require_client_methods(
                    module,
                    client,
                    "NotificationsContacts",
                    {"untag_resource": ("arn", "tagKeys")},
                )
                try:
                    client.untag_resource(
                        arn=contact_arn,
                        tagKeys=tag_keys_to_unset,
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(
                        e,
                        msg=("Unable to remove tags from AWS Notifications contact " f"{contact_arn}"),
                    )

            if tags_to_set:
                require_client_methods(
                    module,
                    client,
                    "NotificationsContacts",
                    {"tag_resource": ("arn", "tags")},
                )
                try:
                    client.tag_resource(
                        arn=contact_arn,
                        tags=tags_to_set,
                        aws_retry=True,
                    )
                except (BotoCoreError, ClientError) as e:
                    module.fail_json_aws(e, msg=f"Unable to tag AWS Notifications contact {contact_arn}")

            contact = apply_tag_deltas(contact, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode:
        if resource_changed:
            contact = dict(desired_contact)
            if desired_tags is not None:
                contact["tags"] = desired_tags
        else:
            contact = apply_tag_deltas(contact, tags_to_set, tag_keys_to_unset)

    module.exit_json(
        changed=changed,
        email_contact=boto3_resource_to_ansible_dict(
            contact, transform_tags=False, force_tags=False, ignore_list=["tags"]
        ),
        state="present",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "email_address": {"required": True, "type": "str"},
            "name": {"type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
            "tags": {"aliases": ["resource_tags"], "type": "dict"},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    state = module.params["state"]

    if state == "present":
        email_address = module.params["email_address"]

        if not 6 <= len(email_address) <= 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+", email_address):
            module.fail_json(msg="email_address must be a valid email address of 6 to 254 characters")

        name = module.params["name"]

        if not 1 <= len(name) <= 64 or not re.search(r"[\w\-.~]", name):
            module.fail_json(
                msg=(
                    "name must be 1 to 64 characters and contain at least "
                    "one letter, digit, underscore, hyphen, period, or tilde"
                )
            )

    require_valid_tags(module, module.params["tags"] if state == "present" else None, 200)
    client = module.client(
        "notificationscontacts",
        retry_decorator=AWSRetry.jittered_backoff(catch_extra_error_codes=["ConflictException"]),
    )
    require_client_methods(
        module,
        client,
        "NotificationsContacts",
        {"list_email_contacts": ("maxResults", "nextToken")},
    )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
