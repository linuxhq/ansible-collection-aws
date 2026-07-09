#!/usr/bin/python
# -*- coding: utf-8 -*-
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
    state: absent
"""

RETURN = r"""
email_contact:
  description:
    - The notifications contact.
    - C(tags) is returned as provided by the AWS Notifications API.
  returned: when a contact exists after module execution
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
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import compare_aws_tags
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def apply_tag_deltas(contact, tags_to_set, tag_keys_to_unset):
    updated = dict(contact)
    updated_tags = dict(updated.get("tags", {}))

    for tag_key in tag_keys_to_unset:
        updated_tags.pop(tag_key, None)
    updated_tags.update(tags_to_set)
    updated["tags"] = updated_tags
    return updated


def get_contact_by_address(client, module):
    email_address = module.params["email_address"]

    try:
        contacts = paginated_query_with_retries(client, "list_email_contacts").get(
            "emailContacts", []
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Notifications contacts")

    for contact in contacts:
        if contact.get("address") == email_address:
            return contact
    return None


def ensure_absent(client, module):
    contact = get_contact_by_address(client, module)
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
    email_address = module.params["email_address"]
    name = module.params["name"]
    tags = module.params["tags"]
    contact = get_contact_by_address(client, module)
    current_contact = (
        {"address": contact.get("address"), "name": contact.get("name")}
        if contact
        else None
    )
    desired_contact = {
        "address": email_address,
        "name": name,
    }
    resource_changed = (current_contact or {}) != desired_contact

    tags_to_set, tag_keys_to_unset = ({}, [])
    if tags is not None and contact is not None and not resource_changed:
        contact = dict(contact)

        try:
            contact["tags"] = client.list_tags_for_resource(
                arn=contact["arn"],
                aws_retry=True,
            ).get("tags", {})
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to list tags for AWS Notifications contact "
                    f"{contact['arn']}"
                ),
            )

        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            contact["tags"],
            tags,
            purge_tags=module.params["purge_tags"],
        )

    changed = bool(resource_changed or tags_to_set or tag_keys_to_unset)

    if changed and not module.check_mode:
        if resource_changed:
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
                            f"{email_address}"
                        ),
                    )

            request = {
                "emailAddress": email_address,
                "name": name,
            }
            if tags is not None:
                request["tags"] = tags

            try:
                contact_arn = client.create_email_contact(
                    **request, aws_retry=True
                ).get("arn")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS Notifications contact {email_address}",
                )

            contact = None
            if contact_arn:
                try:
                    contact = client.get_email_contact(
                        arn=contact_arn,
                        aws_retry=True,
                    ).get("emailContact")
                except is_boto3_error_code("ResourceNotFoundException"):
                    contact = None
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=f"Unable to get AWS Notifications contact {contact_arn}",
                    )

            if contact is None:
                contact = dict(desired_contact, arn=contact_arn)
            if tags is not None:
                contact["tags"] = tags
        else:
            contact_arn = contact["arn"]
            if tag_keys_to_unset:
                try:
                    client.untag_resource(
                        arn=contact_arn,
                        tagKeys=tag_keys_to_unset,
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e,
                        msg=(
                            "Unable to remove tags from AWS Notifications contact "
                            f"{contact_arn}"
                        ),
                    )

            if tags_to_set:
                try:
                    client.tag_resource(
                        arn=contact_arn,
                        tags=tags_to_set,
                        aws_retry=True,
                    )
                except Exception as e:
                    module.fail_json_aws(
                        e, msg=f"Unable to tag AWS Notifications contact {contact_arn}"
                    )

            contact = apply_tag_deltas(contact, tags_to_set, tag_keys_to_unset)
    elif changed and module.check_mode:
        if resource_changed:
            contact = dict(desired_contact)
            if tags is not None:
                contact["tags"] = tags
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
            "tags": {"type": "dict"},
        },
        required_if=[("state", "present", ["name"])],
        supports_check_mode=True,
    )
    state = module.params["state"]
    tags = module.params["tags"]

    if state == "present":
        email_address = module.params["email_address"]

        if not 6 <= len(email_address) <= 254 or not re.fullmatch(
            r".+@.+", email_address
        ):
            module.fail_json(
                msg="email_address must be a valid email address of 6 to 254 characters"
            )

        name = module.params["name"]

        if not 1 <= len(name) <= 64 or not re.search(r"[\w\-.~]", name):
            module.fail_json(
                msg=(
                    "name must be 1 to 64 characters and contain at least "
                    "one letter, digit, underscore, hyphen, period, or tilde"
                )
            )

    client = module.client(
        "notificationscontacts", retry_decorator=AWSRetry.jittered_backoff()
    )
    method_names = {"list_email_contacts"}
    if state == "present":
        method_names.update(
            {"create_email_contact", "delete_email_contact", "get_email_contact"}
        )
        if tags is not None:
            method_names.update({"list_tags_for_resource", "tag_resource"})
            if module.params["purge_tags"]:
                method_names.add("untag_resource")
    elif state == "absent":
        method_names.add("delete_email_contact")
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
                msg=(
                    "Installed botocore does not support "
                    f"NotificationsContacts {method_name}"
                )
            )

    required_method_parameters = {
        "create_email_contact": {"emailAddress", "name"},
        "delete_email_contact": {"arn"},
        "get_email_contact": {"arn"},
        "list_email_contacts": {"maxResults", "nextToken"},
        "list_tags_for_resource": {"arn"},
        "tag_resource": {"arn", "tags"},
        "untag_resource": {"arn", "tagKeys"},
    }
    if state == "present" and tags is not None:
        required_method_parameters["create_email_contact"].add("tags")

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support NotificationsContacts "
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
