#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_find,
    aws_paginated_list,
    aws_request_params,
)


def aws_notification_hub(region):
    return aws_request_params(
        {"notification_hub_region": region},
        capitalize_first=False,
    )


def get_email_contact_by_address(client, module, email_address):
    return aws_paginated_find(
        client,
        module,
        "list_email_contacts",
        "emailContacts",
        lambda contact: contact.get("address") == email_address,
    )


def get_notification_hub_by_region(client, module, region):
    return aws_paginated_find(
        client,
        module,
        "list_notification_hubs",
        "notificationHubs",
        lambda hub: hub.get("notificationHubRegion") == region,
    )


def list_email_contacts(client, module, name=None):
    email_contacts = aws_paginated_list(
        client,
        module,
        "list_email_contacts",
        "emailContacts",
    )
    return (
        [contact for contact in email_contacts if contact.get("name") == name]
        if name is not None
        else email_contacts
    )


def list_notification_hubs(client, module):
    return aws_paginated_list(
        client,
        module,
        "list_notification_hubs",
        "notificationHubs",
    )
