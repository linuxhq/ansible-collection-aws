#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox
short_description: Manage AWS Simple Email Service account details
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
attributes:
  check_mode:
    description: The module reports the account state that would result from submitting the request.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
  contains:
    dedicated_ip_auto_warmup_enabled:
      description: Whether dedicated IP address warm-up is enabled for the account.
      returned: when available
      type: bool
    details:
      description: The submitted SES account details.
      returned: when available
      type: dict
      contains:
        additional_contact_email_addresses:
          description: Additional contact email addresses associated with the request.
          returned: when available
          type: list
          elements: str
        contact_language:
          description: Contact language submitted with the request, returned as V(EN) or V(JA).
          returned: when available
          type: str
        mail_type:
          description: Mail type submitted with the request, returned as V(MARKETING) or V(TRANSACTIONAL).
          returned: when available
          type: str
        review_details:
          description: Details of the AWS review of the production access request.
          returned: when available
          type: dict
          contains:
            case_id:
              description: Identifier of the support case associated with the review.
              returned: when available
              type: str
            status:
              description: Status of the review.
              returned: when available
              type: str
        use_case_description:
          description: Description of the intended SES use case.
          returned: when available
          type: str
        website_url:
          description: Website URL associated with the request.
          returned: when available
          type: str
    enforcement_status:
      description: The enforcement status of the account.
      returned: when available
      type: str
    pricing_attributes:
      description: Pricing plan details for the account.
      returned: when available
      type: dict
      contains:
        current_plan:
          description: Current pricing plan for the account.
          returned: when available
          type: str
        next_plan:
          description: Pricing plan scheduled for the account.
          returned: when available
          type: str
    production_access_enabled:
      description: Whether production access is enabled for the account.
      returned: when available
      type: bool
    send_quota:
      description: Sending limits and recent usage for the account.
      returned: when available
      type: dict
      contains:
        max24_hour_send:
          description: Maximum number of emails that can be sent in a 24-hour period.
          returned: when available
          type: float
        max_send_rate:
          description: Maximum number of emails that can be sent per second.
          returned: when available
          type: float
        sent_last24_hours:
          description: Number of emails sent during the previous 24 hours.
          returned: when available
          type: float
    sending_enabled:
      description: Whether the account can send email.
      returned: when available
      type: bool
    suppression_attributes:
      description: Account-level suppression settings.
      returned: when available
      type: dict
      contains:
        suppressed_reasons:
          description: Reasons for which recipient addresses are added to the suppression list.
          returned: when available
          type: list
          elements: str
        validation_attributes:
          description: Suppression-list validation settings for the account.
          returned: when available
          type: dict
          contains:
            condition_threshold:
              description: Validation condition threshold settings.
              returned: when available
              type: dict
              contains:
                condition_threshold_enabled:
                  description: Condition threshold state, V(ENABLED) or V(DISABLED).
                  returned: when available
                  type: str
                overall_confidence_threshold:
                  description: Overall confidence threshold settings.
                  returned: when available
                  type: dict
                  contains:
                    confidence_verdict_threshold:
                      description: Confidence verdict threshold, V(MEDIUM), V(HIGH), or V(MANAGED).
                      returned: when available
                      type: str
    vdm_attributes:
      description: Virtual Deliverability Manager settings for the account.
      returned: when available
      type: dict
      contains:
        dashboard_attributes:
          description: Virtual Deliverability Manager dashboard settings.
          returned: when available
          type: dict
          contains:
            engagement_metrics:
              description: Engagement metrics state, V(ENABLED) or V(DISABLED).
              returned: when available
              type: str
        guardian_attributes:
          description: Virtual Deliverability Manager Guardian settings.
          returned: when available
          type: dict
          contains:
            optimized_shared_delivery:
              description: Optimized shared delivery state, V(ENABLED) or V(DISABLED).
              returned: when available
              type: str
        vdm_enabled:
          description: Virtual Deliverability Manager state, V(ENABLED) or V(DISABLED).
          returned: when available
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ses import get_account

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
    normalized = {field: details[field] for field in ACCOUNT_DETAILS_FIELDS if details.get(field)}
    if normalized.get("additional_contact_email_addresses"):
        normalized["additional_contact_email_addresses"] = sorted(set(normalized["additional_contact_email_addresses"]))

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

    if len(set(module.params["additional_contact_email_addresses"])) > 4:
        module.fail_json(msg="additional_contact_email_addresses must contain at most 4 addresses")

    use_case_description = module.params["use_case_description"]
    website_url = module.params["website_url"]
    if use_case_description is not None and (not use_case_description.strip() or not website_url.strip()):
        module.fail_json(msg="use_case_description and website_url must be non-empty strings")

    ready = use_case_description is not None and website_url is not None

    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    methods = {"get_account": ()}
    if ready:
        methods["put_account_details"] = (
            "AdditionalContactEmailAddresses",
            "ContactLanguage",
            "MailType",
            "ProductionAccessEnabled",
            "UseCaseDescription",
            "WebsiteURL",
        )

    require_client_methods(
        module,
        client,
        "SESv2",
        methods,
    )

    current_account = get_account(client, module)
    desired_details = comparable_details(
        {
            "additional_contact_email_addresses": module.params["additional_contact_email_addresses"],
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
        "production_access_enabled": current_account.get("production_access_enabled", False),
    }

    changed = ready and current != desired

    if changed and not module.check_mode:
        try:
            client.put_account_details(**request, aws_retry=True)
        except is_boto3_error_code("ConflictException"):
            module.warn("AWS Simple Email Service account details request is already in progress")
            changed = False
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg="Unable to manage AWS Simple Email Service account details")

        if changed:
            current_account = dict(current_account)
            current_account.update(desired)
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
