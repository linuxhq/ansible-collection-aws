#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: acm_certificate_request
short_description: Manage aws certificate manager certificates
description:
  - Requests AWS Certificate Manager certificates using DNS validation.
  - An existing certificate is reused instead of requesting a new one when it
    is C(AMAZON_ISSUED), uses DNS validation, is C(PENDING_VALIDATION) or
    C(ISSUED), and its domain name and subject alternative names match; the
    most recently created certificate is reused when several match.
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
      - ACM requires a token of 1 to 32 ASCII word characters.
      - This option is only used when requesting a certificate.
    type: str
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed from the certificate.
      - This option is only applied when O(tags) is provided.
    default: true
    type: bool
  subject_alternative_names:
    description:
      - Subject alternative names for the certificate.
    elements: str
    type: list
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
    - ARN of the matching or requested certificate.
  returned: except when a new certificate would be requested in check mode
  type: str
"""

import hashlib
import json
import re

from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
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

    domain_name = module.params["domain_name"]
    idempotency_token = module.params["idempotency_token"]
    purge_tags = module.params["purge_tags"]
    subject_alternative_names = module.params["subject_alternative_names"]
    tags = module.params["tags"]

    if idempotency_token is not None and not re.fullmatch(
        r"\w{1,32}", idempotency_token, flags=re.ASCII
    ):
        module.fail_json(
            msg="ACM certificate request idempotency_token must be 1 to 32 ASCII word characters"
        )

    client = module.client("acm", retry_decorator=AWSRetry.jittered_backoff())

    methods = {
        "describe_certificate": (),
        "list_certificates": (),
        "request_certificate": (),
    }
    if tags is not None:
        methods["add_tags_to_certificate"] = ()
        methods["list_tags_for_certificate"] = ()
        if purge_tags:
            methods["remove_tags_from_certificate"] = ()

    require_client_methods(module, client, "AWS Certificate Manager", methods)

    normalized_domain_name = domain_name.lower()
    desired_names = {normalized_domain_name}
    for name in subject_alternative_names or []:
        desired_names.add(name.lower())

    summaries = query_list(
        module,
        client,
        "list_certificates",
        "CertificateSummaryList",
        "Unable to list AWS Certificate Manager certificates",
        CertificateStatuses=["PENDING_VALIDATION", "ISSUED"],
    )

    matched = None
    for summary in summaries:
        if summary.get("DomainName", "").lower() != normalized_domain_name:
            continue

        certificate_arn = summary["CertificateArn"]

        try:
            certificate = client.describe_certificate(
                CertificateArn=certificate_arn,
                aws_retry=True,
            ).get("Certificate", {})
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=(
                    "Unable to describe AWS Certificate Manager certificate "
                    f"{certificate_arn}"
                ),
            )

        if certificate.get("Type") != "AMAZON_ISSUED":
            continue

        validation_methods = set()
        for option in certificate.get("DomainValidationOptions", []):
            validation_methods.add(option.get("ValidationMethod"))

        if validation_methods != {"DNS"}:
            continue

        certificate_names = set()
        for name in certificate.get("SubjectAlternativeNames", []):
            certificate_names.add(name.lower())

        if certificate_names != desired_names:
            continue

        if matched is None or certificate["CreatedAt"] > matched["CreatedAt"]:
            matched = certificate

    created = matched is None

    if created:
        if module.check_mode:
            module.exit_json(changed=True)

        if idempotency_token is None:
            token_data = {
                "domain_name": normalized_domain_name,
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
                "Tags": ansible_dict_to_boto3_tag_list(tags) if tags else None,
                "ValidationMethod": "DNS",
            }
        )

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
    else:
        certificate_arn = matched["CertificateArn"]

    changed = created

    if not created and tags is not None:
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
            purge_tags=purge_tags,
        )

        changed = bool(tags_to_set or tag_keys_to_unset)

        if tag_keys_to_unset and not module.check_mode:
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

        if tags_to_set and not module.check_mode:
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
        changed=changed,
        certificate_arn=certificate_arn,
    )


if __name__ == "__main__":
    main()
