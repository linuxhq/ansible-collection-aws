#!/usr/bin/python
# -*- coding: utf-8 -*-

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
proposed_account:
  description:
    - Predicted AWS Simple Email Service account values after the request.
  returned: when changed
  type: dict
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def get_account(client, module):
    try:
        response = client.get_account()
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to get AWS Simple Email Service account details"
        )
    return response


def build_request(module):
    request = {
        "ContactLanguage": module.params["contact_language"].upper(),
        "MailType": module.params["mail_type"].upper(),
        "ProductionAccessEnabled": True,
    }

    if module.params["additional_contact_email_addresses"]:
        request["AdditionalContactEmailAddresses"] = module.params[
            "additional_contact_email_addresses"
        ]
    if module.params["use_case_description"] is not None:
        request["UseCaseDescription"] = module.params["use_case_description"].strip()
    if module.params["website_url"] is not None:
        request["WebsiteURL"] = module.params["website_url"]

    return request


def build_proposed_account(account, request):
    proposed = dict(account)
    proposed["ProductionAccessEnabled"] = True
    details = dict(account.get("Details", {}))

    for key in (
        "AdditionalContactEmailAddresses",
        "ContactLanguage",
        "MailType",
        "UseCaseDescription",
        "WebsiteURL",
    ):
        if key in request:
            details[key] = request[key]

    proposed["Details"] = details
    return proposed


def main() -> None:
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
        "validate_certs": {"default": True, "type": "bool"},
        "website_url": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("sesv2")

    current_account = get_account(client, module)
    request = build_request(module)

    ready = (
        not current_account.get("ProductionAccessEnabled", False)
        and module.params["use_case_description"] is not None
        and module.params["website_url"] is not None
    )
    changed = ready
    proposed_account = build_proposed_account(current_account, request)

    if changed and not module.check_mode:
        try:
            client.put_account_details(**request)
        except Exception as e:
            if (
                getattr(e, "response", {}).get("Error", {}).get("Code")
                == "ConflictException"
            ):
                module.warn(
                    "AWS Simple Email Service account details request is already in progress"
                )
                current_account = get_account(client, module)
                changed = False
            else:
                module.fail_json_aws(
                    e, msg="Unable to manage AWS Simple Email Service account details"
                )
        else:
            current_account = get_account(client, module)
            proposed_account = current_account

    result = {
        "changed": changed,
        "account": camel_dict_to_snake_dict(current_account),
    }

    if changed:
        result["proposed_account"] = camel_dict_to_snake_dict(proposed_account)

    module.exit_json(**result)


if __name__ == "__main__":
    main()
