#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)


def list_email_contacts(client, module):
    try:
        response = paginated_query_with_retries(client, "list_email_contacts")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS Notifications contacts",
        )
    return response.get("emailContacts", [])


def list_notification_hubs(client, module):
    try:
        response = paginated_query_with_retries(client, "list_notification_hubs")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS Notifications hubs",
        )
    return response.get("notificationHubs", [])
