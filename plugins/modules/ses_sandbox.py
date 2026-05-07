#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox
version_added: "1.9.0"
short_description: Manage AWS Simple Email Service account details
description:
  - Requests production access for an AWS Simple Email Service account and manages the submitted account details.
author:
  - Taylor Kimball (@tkimball83)
options:
  additional_contact_email_addresses:
    description:
      - Additional contact email addresses to associate with the request.
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
    type: str
  website_url:
    description:
      - Website URL associated with the SES account request.
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

from ansible.module_utils.common.dict_transformations import recursive_diff
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)

ACCOUNT_DETAILS_FIELDS = (
    "additional_contact_email_addresses",
    "contact_language",
    "mail_type",
    "use_case_description",
    "website_url",
)


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

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    current_account = boto3_resource_to_ansible_dict(
        client.get_account(aws_retry=True), transform_tags=False, force_tags=False
    )
    desired_details = {
        "additional_contact_email_addresses": (
            module.params["additional_contact_email_addresses"] or None
        ),
        "contact_language": module.params["contact_language"].upper(),
        "mail_type": module.params["mail_type"].upper(),
        "use_case_description": (
            None
            if module.params["use_case_description"] is None
            else module.params["use_case_description"].strip()
        ),
        "website_url": module.params["website_url"],
    }
    desired = {
        "details": desired_details,
        "production_access_enabled": True,
    }
    request = scrub_none_parameters(
        {
            "AdditionalContactEmailAddresses": desired_details[
                "additional_contact_email_addresses"
            ],
            "ContactLanguage": desired_details["contact_language"],
            "MailType": desired_details["mail_type"],
            "ProductionAccessEnabled": True,
            "UseCaseDescription": desired_details["use_case_description"],
            "WebsiteURL": desired_details["website_url"],
        }
    )
    current = {
        "details": current_account.get("details", {}),
        "production_access_enabled": current_account.get(
            "production_access_enabled", False
        ),
    }
    current = {
        "details": {
            field: current["details"].get(field)
            for field in ACCOUNT_DETAILS_FIELDS
            if current["details"].get(field) is not None
        },
        "production_access_enabled": current["production_access_enabled"],
    }

    ready = (
        module.params["use_case_description"] is not None
        and module.params["website_url"] is not None
    )
    changed = ready and recursive_diff((current) or {}, (desired) or {}) is not None

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
        current_account = boto3_resource_to_ansible_dict(
            client.get_account(aws_retry=True),
            transform_tags=False,
            force_tags=False,
        )

    result = {
        "changed": changed,
        "account": current_account,
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
