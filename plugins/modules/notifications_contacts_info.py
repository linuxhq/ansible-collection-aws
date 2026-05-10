#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts_info
version_added: "1.9.5"
short_description: Gather information about AWS Notifications contacts
description:
  - Gathers information about AWS Notifications email contacts.
author:
  - Taylor Kimball (@tkimball83)
options:
  arns:
    description:
      - AWS Notifications contact ARNs used to limit the result set.
    elements: str
    type: list
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
    arns:
      - arn:aws:notifications-contacts::123456789012:emailcontact/example
"""

RETURN = r"""
email_contacts:
  description:
    - The notifications contacts.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def contact_with_tags(client, module, contact):
    if not contact.get("arn"):
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


def get_email_contact(client, module, arn):
    try:
        return client.get_email_contact(arn=arn, aws_retry=True).get("emailContact")
    except is_boto3_error_code("ResourceNotFoundException"):
        return None
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Notifications contact {arn}",
        )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "arns": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "notificationscontacts", retry_decorator=AWSRetry.jittered_backoff()
    )
    if module.params["arns"]:
        email_contacts = [
            contact
            for contact in [
                get_email_contact(client, module, arn) for arn in module.params["arns"]
            ]
            if contact is not None
        ]
    else:
        email_contacts = paginated_query_with_retries(
            client, "list_email_contacts"
        ).get("emailContacts", [])

    module.exit_json(
        changed=False,
        email_contacts=boto3_resource_list_to_ansible_dict(
            [contact_with_tags(client, module, contact) for contact in email_contacts],
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
