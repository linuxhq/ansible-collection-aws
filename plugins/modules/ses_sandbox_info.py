#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_sandbox_info
short_description: Gather information about AWS Simple Email Service account details
description:
  - Gathers information about AWS Simple Email Service account details.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module does not modify AWS resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about SES account details
  linuxhq.aws.ses_sandbox_info:
"""

RETURN = r"""
account:
  description:
    - Information about the AWS Simple Email Service account.
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ses import get_account


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SESv2",
        {"get_account": ()},
    )

    module.exit_json(
        changed=False,
        account=get_account(client, module),
    )


if __name__ == "__main__":
    main()
