#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: acm_certificate_request
short_description: Manage aws certificate manager certificates
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
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed from the certificate.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  tags:
    description:
      - Tags to apply to the certificate.
    type: dict
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
    tags:
      Name: www.example.com
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

from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)


def update_certificate_tags(client, module, certificate_arn):
    if module.params["tags"] is None:
        return

    try:
        current_tags = boto3_tag_list_to_ansible_dict(
            client.list_tags_for_certificate(
                CertificateArn=certificate_arn,
                aws_retry=True,
            ).get("Tags", [])
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Certificate Manager certificate {certificate_arn}",
        )

    tags_to_set, tag_keys_to_unset = compare_aws_tags(
        current_tags,
        module.params["tags"],
        purge_tags=module.params["purge_tags"],
    )

    if tag_keys_to_unset:
        try:
            client.remove_tags_from_certificate(
                CertificateArn=certificate_arn,
                Tags=[{"Key": key} for key in tag_keys_to_unset],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from AWS Certificate Manager certificate {certificate_arn}",
            )

    if tags_to_set:
        try:
            client.add_tags_to_certificate(
                CertificateArn=certificate_arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag AWS Certificate Manager certificate {certificate_arn}",
            )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"required": True, "type": "str"},
            "idempotency_token": {"no_log": False, "type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "subject_alternative_names": {"elements": "str", "type": "list"},
            "tags": {"type": "dict"},
        },
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(changed=True)

    client = module.client("acm", retry_decorator=AWSRetry.jittered_backoff())
    idempotency_token = module.params["idempotency_token"]
    if not idempotency_token:
        token_data = {
            "domain_name": module.params["domain_name"].lower(),
            "subject_alternative_names": sorted(
                name.lower()
                for name in module.params["subject_alternative_names"] or []
            ),
        }
        idempotency_token = hashlib.sha256(
            to_bytes(json.dumps(token_data, separators=(",", ":"), sort_keys=True))
        ).hexdigest()[:32]

    params = {
        "DomainName": module.params["domain_name"],
        "IdempotencyToken": idempotency_token,
        "ValidationMethod": "DNS",
    }
    if module.params["subject_alternative_names"]:
        params["SubjectAlternativeNames"] = module.params["subject_alternative_names"]
    if module.params["tags"] is not None:
        params["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])

    try:
        certificate_arn = client.request_certificate(**params, aws_retry=True).get(
            "CertificateArn"
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to request AWS Certificate Manager certificate "
                f"{module.params['domain_name']}"
            ),
        )

    update_certificate_tags(client, module, certificate_arn)

    module.exit_json(
        changed=True,
        certificate_arn=certificate_arn,
    )


if __name__ == "__main__":
    main()
