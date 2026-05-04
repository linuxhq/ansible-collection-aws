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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"required": True, "type": "str"},
            "subject_alternative_names": {"elements": "str", "type": "list"},
        },
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(changed=True)

    client = module.client("acm")
    params = {
        "DomainName": module.params["domain_name"],
        "ValidationMethod": "DNS",
    }
    if module.params["subject_alternative_names"]:
        params["SubjectAlternativeNames"] = module.params["subject_alternative_names"]

    try:
        response = client.request_certificate(**params)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to request AWS Certificate Manager certificate {module.params['domain_name']}",
        )

    module.exit_json(
        changed=True,
        certificate_arn=response.get("CertificateArn"),
    )


if __name__ == "__main__":
    main()
