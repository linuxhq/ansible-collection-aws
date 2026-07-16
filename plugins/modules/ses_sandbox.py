#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox
short_description: Manage aws simple email service account details
description:
  - Requests production access for an AWS Simple Email Service account and manages the submitted account details.
  - Without O(use_case_description) and O(website_url) the module only
    reports the current account details.
author:
  - Taylor Kimball (@tkimball83)
options:
  additional_contact_email_addresses:
    description:
      - Additional contact email addresses to associate with the request.
      - This must contain at most 4 email addresses.
    default: []
    elements: str
    type: list
  contact_language:
    description:
      - Contact language to submit with the request.
    choices:
      - en
      - ja
    default: en
    type: str
  mail_type:
    description:
      - Mail type to submit with the request.
    choices:
      - marketing
      - transactional
    default: transactional
    type: str
  use_case_description:
    description:
      - Description of the intended SES use case.
      - This is required with O(website_url) to request production access.
    type: str
  website_url:
    description:
      - Website URL associated with the SES account request.
      - This is required with O(use_case_description) to request production access.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Request SES production access
  linuxhq.aws.ses_sandbox:
    additional_contact_email_addresses:
      - jake@molecule.org
      - john@molecule.org
    use_case_description: New account creation
    website_url: https://github.com/ansible/molecule
"""

RETURN = r"""
account:
  description:
    - Information about the AWS Simple Email Service account after the request.
  returned: always
  type: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ses import (
    get_account,
)

ACCOUNT_DETAILS_FIELDS = (
    "additional_contact_email_addresses",
    "contact_language",
    "mail_type",
    "use_case_description",
    "website_url",
)
ACCOUNT_DETAILS_REQUEST_FIELDS = (
    ("AdditionalContactEmailAddresses", "additional_contact_email_addresses"),
    ("ContactLanguage", "contact_language"),
    ("MailType", "mail_type"),
    ("UseCaseDescription", "use_case_description"),
    ("WebsiteURL", "website_url"),
)


def comparable_details(details):
    normalized = {
        field: details[field] for field in ACCOUNT_DETAILS_FIELDS if details.get(field)
    }
    if normalized.get("additional_contact_email_addresses"):
        normalized["additional_contact_email_addresses"] = sorted(
            set(normalized["additional_contact_email_addresses"])
        )
    return normalized


def main():
    argument_spec = {
        "additional_contact_email_addresses": {
            "default": [],
            "elements": "str",
            "type": "list",
        },
        "contact_language": {"choices": ["en", "ja"], "default": "en", "type": "str"},
        "mail_type": {
            "choices": ["marketing", "transactional"],
            "default": "transactional",
            "type": "str",
        },
        "use_case_description": {"type": "str"},
        "website_url": {"type": "str"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_together=[["use_case_description", "website_url"]],
        supports_check_mode=True,
    )

    if len(module.params["additional_contact_email_addresses"]) > 4:
        module.fail_json(
            msg="additional_contact_email_addresses must contain at most 4 addresses"
        )

    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SESv2",
        {
            "get_account": (),
            "put_account_details": (
                "AdditionalContactEmailAddresses",
                "ContactLanguage",
                "MailType",
                "ProductionAccessEnabled",
                "UseCaseDescription",
                "WebsiteURL",
            ),
        },
    )

    current_account = get_account(client, module)
    use_case_description = module.params["use_case_description"]
    website_url = module.params["website_url"]
    desired_details = comparable_details(
        {
            "additional_contact_email_addresses": module.params[
                "additional_contact_email_addresses"
            ],
            "contact_language": module.params["contact_language"].upper(),
            "mail_type": module.params["mail_type"].upper(),
            "use_case_description": (use_case_description or "").strip(),
            "website_url": website_url,
        }
    )
    desired = {
        "details": desired_details,
        "production_access_enabled": True,
    }
    request = {"ProductionAccessEnabled": True}
    for request_field, details_field in ACCOUNT_DETAILS_REQUEST_FIELDS:
        if details_field in desired_details:
            request[request_field] = desired_details[details_field]

    current = {
        "details": comparable_details(current_account.get("details") or {}),
        "production_access_enabled": current_account.get(
            "production_access_enabled", False
        ),
    }

    ready = use_case_description is not None and website_url is not None
    changed = ready and current != desired

    if changed and not module.check_mode:
        try:
            client.put_account_details(**request, aws_retry=True)
        except is_boto3_error_code("ConflictException"):
            module.warn(
                "AWS Simple Email Service account details request is already in progress"
            )
            changed = False
        except Exception as e:
            module.fail_json_aws(
                e, msg="Unable to manage AWS Simple Email Service account details"
            )

        current_account = get_account(client, module)
    elif changed and module.check_mode:
        current_account = dict(current_account)
        current_account.update(desired)

    result = {
        "changed": changed,
        "account": current_account,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
