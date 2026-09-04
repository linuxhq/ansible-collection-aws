#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts_info
short_description: Gather information about AWS Notifications contacts
description:
  - Gathers information about AWS Notifications email contacts.
author:
  - Taylor Kimball (@tkimball83)
options:
  arn:
    description:
      - AWS Notifications contact ARN used to limit the result set.
      - An ARN that does not exist results in an empty list.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: The module only retrieves information from AWS.
    support: full
"""

EXAMPLES = r"""
- name: Gather information about AWS Notifications contacts
  linuxhq.aws.notifications_contacts_info:

- name: Gather information about a single AWS Notifications contact
  linuxhq.aws.notifications_contacts_info:
    arn: arn:aws:notifications-contacts::123456789012:emailcontact/example
"""

RETURN = r"""
email_contacts:
  description:
    - The notifications contacts.
  returned: always
  type: list
  elements: dict
  contains:
    address:
      description: The contact email address.
      returned: always
      type: str
    arn:
      description: The contact ARN.
      returned: always
      type: str
    creation_time:
      description: The date and time when the contact was created.
      returned: always
      type: str
    name:
      description: The contact name.
      returned: always
      type: str
    status:
      description: The contact activation status.
      returned: always
      type: str
    tags:
      description: The contact tags.
      returned: always
      type: dict
    update_time:
      description: The date and time when the contact was last updated.
      returned: always
      type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_contact(module, contact, operation):
    valid_strings = ("address", "arn", "name", "status")
    if (
        not isinstance(contact, dict)
        or not all(isinstance(contact.get(key), str) and contact[key] for key in valid_strings)
        or contact.get("creationTime") is None
        or contact.get("updateTime") is None
    ):
        module.fail_json(msg=f"{operation}: AWS returned an invalid contact")
    return contact


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "arn": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("notificationscontacts", retry_decorator=AWSRetry.jittered_backoff())

    arn = module.params["arn"]
    methods = {}
    if arn:
        methods["get_email_contact"] = ("arn",)
    else:
        methods["list_email_contacts"] = ("maxResults", "nextToken")

    require_client_methods(module, client, "NotificationsContacts", methods)

    if arn:
        try:
            response = client.get_email_contact(arn=arn, aws_retry=True)
        except is_boto3_error_code("ResourceNotFoundException"):
            response = {"emailContact": None}
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS Notifications contact {arn}",
            )

        if not isinstance(response, dict) or "emailContact" not in response:
            module.fail_json(msg=f"Unable to get AWS Notifications contact {arn}: AWS returned an invalid response")
        contact = response.get("emailContact")
        if contact is not None:
            validate_contact(module, contact, f"Unable to get AWS Notifications contact {arn}")

        email_contacts = [contact] if contact is not None else []
    else:
        email_contacts = query_list(
            module,
            client,
            "list_email_contacts",
            "emailContacts",
            "Unable to list AWS Notifications contacts",
        )

    if not isinstance(email_contacts, list):
        module.fail_json(msg="Unable to list AWS Notifications contacts: AWS returned an invalid response")
    for contact in email_contacts:
        validate_contact(module, contact, "Unable to list AWS Notifications contacts")

    if email_contacts:
        require_client_methods(
            module,
            client,
            "NotificationsContacts",
            {"list_tags_for_resource": ("arn",)},
        )

    email_contacts_with_tags = []
    for contact in email_contacts:
        contact = dict(contact)

        try:
            tag_response = client.list_tags_for_resource(
                arn=contact["arn"],
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list tags for AWS Notifications contact {contact['arn']}",
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

        email_contacts_with_tags.append(contact)

    module.exit_json(
        changed=False,
        email_contacts=boto3_resource_list_to_ansible_dict(
            email_contacts_with_tags,
            transform_tags=False,
            force_tags=False,
            ignore_list=["tags"],
        ),
    )


if __name__ == "__main__":
    main()
