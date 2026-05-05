#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: acm_certificate_request
version_added: 1.9.1
short_description: Request AWS ACM certificates
description:
  - Requests AWS Certificate Manager certificates using DNS validation.
author:
  - Taylor Kimball (@tkimball83)
options:
  domain_name:
    description:
      - Fully qualified domain name for the certificate.
    required: true
    type: str
  idempotency_token:
    description:
      - Custom ACM idempotency token for the certificate request.
      - When omitted, a deterministic token is generated from O(domain_name) and O(subject_alternative_names).
      - ACM requires a token of 32 or fewer word characters.
    type: str
  subject_alternative_names:
    description:
      - Subject alternative names for the certificate.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Request an ACM certificate
  linuxhq.aws.acm_certificate_request:
    domain_name: www.example.com
    subject_alternative_names:
      - example.com
"""

RETURN = r"""
certificate_arn:
  description:
    - ARN of the requested certificate.
  returned: success
  type: str
"""

import hashlib
import json
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_response,
)


def build_idempotency_token(domain_name, subject_alternative_names):
    token_data = {
        "domain_name": domain_name.lower(),
        "subject_alternative_names": sorted(
            name.lower() for name in subject_alternative_names or []
        ),
    }
    return hashlib.sha256(
        json.dumps(token_data, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()[:32]


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"required": True, "type": "str"},
            "idempotency_token": {"type": "str"},
            "subject_alternative_names": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(changed=True)

    client = module.client("acm")
    params = scrub_none_parameters(
        {
            "DomainName": module.params["domain_name"],
            "IdempotencyToken": module.params["idempotency_token"]
            or build_idempotency_token(
                module.params["domain_name"],
                module.params["subject_alternative_names"],
            ),
            "SubjectAlternativeNames": module.params["subject_alternative_names"]
            or None,
            "ValidationMethod": "DNS",
        }
    )

    response = aws_response(
        client,
        module,
        "request_certificate",
        error_message=(
            "Unable to request AWS Certificate Manager certificate "
            f"{module.params['domain_name']}"
        ),
        **params,
    )

    module.exit_json(
        changed=True,
        certificate_arn=response.get("CertificateArn"),
    )


if __name__ == "__main__":
    main()
