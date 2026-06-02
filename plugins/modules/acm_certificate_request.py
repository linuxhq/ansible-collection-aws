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
      - ACM requires a token of 32 or fewer ASCII word characters.
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
  returned: when not in check mode
  type: str
"""

import hashlib
import json
import re

from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
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

    client = module.client("acm", retry_decorator=AWSRetry.jittered_backoff())
    domain_name = module.params["domain_name"]
    idempotency_token = module.params["idempotency_token"]
    subject_alternative_names = module.params["subject_alternative_names"]
    tags = module.params["tags"]

    method_names = ["request_certificate"]
    if tags is not None:
        method_names.extend(
            [
                "add_tags_to_certificate",
                "list_tags_for_certificate",
                "remove_tags_from_certificate",
            ]
        )

    for method_name in method_names:
        try:
            get_boto3_client_method_parameters(client, method_name)
        except Exception:
            module.fail_json(
                msg=(
                    "Installed botocore does not support AWS Certificate "
                    f"Manager {method_name}"
                )
            )

    if idempotency_token is not None and not re.fullmatch(
        r"\w{1,32}", idempotency_token, flags=re.ASCII
    ):
        module.fail_json(
            msg="ACM certificate request idempotency_token must be 1 to 32 ASCII word characters"
        )

    if idempotency_token is None:
        token_data = {
            "domain_name": domain_name.lower(),
            "subject_alternative_names": sorted(
                name.lower() for name in subject_alternative_names or []
            ),
        }
        idempotency_token = hashlib.sha256(
            to_bytes(json.dumps(token_data, separators=(",", ":"), sort_keys=True))
        ).hexdigest()[:32]

    request = scrub_none_parameters(
        {
            "DomainName": domain_name,
            "IdempotencyToken": idempotency_token,
            "SubjectAlternativeNames": subject_alternative_names or None,
            "Tags": (
                ansible_dict_to_boto3_tag_list(tags) if tags is not None else None
            ),
            "ValidationMethod": "DNS",
        }
    )

    if module.check_mode:
        module.exit_json(changed=True)

    try:
        certificate_arn = client.request_certificate(**request, aws_retry=True).get(
            "CertificateArn"
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to request AWS Certificate Manager certificate "
                f"{domain_name}"
            ),
        )

    if tags is not None:
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
                msg=(
                    "Unable to list tags for AWS Certificate Manager "
                    f"certificate {certificate_arn}"
                ),
            )

        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current_tags,
            tags,
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
                    msg=(
                        "Unable to remove tags from AWS Certificate Manager "
                        f"certificate {certificate_arn}"
                    ),
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
                    msg=(
                        "Unable to tag AWS Certificate Manager certificate "
                        f"{certificate_arn}"
                    ),
                )

    module.exit_json(
        changed=True,
        certificate_arn=certificate_arn,
    )


if __name__ == "__main__":
    main()
