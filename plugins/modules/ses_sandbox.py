#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox
version_added: 1.9.1
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ses import (
    get_account,
    normalize_account,
)


def build_request(params):
    return scrub_none_parameters(
        {
            "AdditionalContactEmailAddresses": params[
                "additional_contact_email_addresses"
            ]
            or None,
            "ContactLanguage": params["contact_language"].upper(),
            "MailType": params["mail_type"].upper(),
            "ProductionAccessEnabled": True,
            "UseCaseDescription": (
                None
                if params["use_case_description"] is None
                else params["use_case_description"].strip()
            ),
            "WebsiteURL": params["website_url"],
        }
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
    client = module.client("sesv2")

    current_account = get_account(client, module)
    request = build_request(module.params)

    ready = (
        not current_account.get("ProductionAccessEnabled", False)
        and module.params["use_case_description"] is not None
        and module.params["website_url"] is not None
    )
    changed = ready

    if changed and not module.check_mode:
        put_account_details = AWSRetry.jittered_backoff()(client.put_account_details)
        try:
            put_account_details(**request)
        except is_boto3_error_code("ConflictException"):
            module.warn(
                "AWS Simple Email Service account details request is already in progress"
            )
            current_account = get_account(client, module)
            changed = False
        except Exception as e:
            module.fail_json_aws(
                e, msg="Unable to manage AWS Simple Email Service account details"
            )
        else:
            current_account = get_account(client, module)

    result = {
        "changed": changed,
        "account": normalize_account(current_account),
    }

    module.exit_json(**result)


if __name__ == "__main__":
    main()
