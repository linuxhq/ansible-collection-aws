#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: notifications_contacts_info
short_description: Gather information about aws notifications contacts
description:
  - Gathers information about AWS Notifications email contacts.
author:
  - Taylor Kimball (@tkimball83)
options:
  arn:
    description:
      - AWS Notifications contact ARN used to limit the result set.
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
    arn: arn:aws:notifications-contacts::123456789012:emailcontact/example
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
    get_boto3_client_method_parameters,
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "arn": {"type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client(
        "notificationscontacts", retry_decorator=AWSRetry.jittered_backoff()
    )

    for method_name in (
        "get_email_contact",
        "list_email_contacts",
        "list_tags_for_resource",
    ):
        try:
            get_boto3_client_method_parameters(client, method_name)
        except Exception:
            module.fail_json(
                msg=(
                    "Installed botocore does not support AWS Notifications Contacts "
                    f"{method_name}"
                )
            )

    if module.params["arn"]:
        try:
            contact = client.get_email_contact(
                arn=module.params["arn"], aws_retry=True
            ).get("emailContact")
        except is_boto3_error_code("ResourceNotFoundException"):
            contact = None
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS Notifications contact {module.params['arn']}",
            )

        email_contacts = [contact] if contact is not None else []
    else:
        try:
            email_contacts = paginated_query_with_retries(
                client, "list_email_contacts"
            ).get("emailContacts", [])
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to list AWS Notifications contacts")

    email_contacts_with_tags = []
    for contact in email_contacts:
        if not contact.get("arn"):
            email_contacts_with_tags.append(contact)
            continue

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

        email_contacts_with_tags.append(contact)

    module.exit_json(
        changed=False,
        email_contacts=boto3_resource_list_to_ansible_dict(
            email_contacts_with_tags,
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
