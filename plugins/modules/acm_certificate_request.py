#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: acm_certificate_request
version_added: "1.9.0"
short_description: Manage AWS Certificate Manager certificates
description:
  - Requests AWS Certificate Manager certificates using DNS validation.
  - An existing certificate is reused instead of requesting a new one when it
    is C(AMAZON_ISSUED), uses DNS validation, is C(PENDING_VALIDATION) or
    C(ISSUED), and its domain name and subject alternative names match; the
    most recently created certificate is reused when several match.
  - Certificates managed by another AWS service, such as CloudFront, are never reused.
  - Reusing an existing certificate requires botocore C(1.38.4) or later so
    that certificates managed by another AWS service can be identified. A new
    certificate can still be requested with older botocore releases when no
    existing certificate matches.
  - ACM permits at most 50 tags on a certificate; tag keys must contain 1 to
    128 characters and tag values may contain at most 256 characters.
  - Existing certificate tags are purged only when O(tags) is provided and
    O(purge_tags=true).
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
  subject_alternative_names:
    description:
      - Subject alternative names for the certificate.
      - This must contain at most 99 additional entries after normalization because ACM allows 100 domain names including O(domain_name).
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts certificate requests and tag changes without modifying AWS resources.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.text.converters import to_bytes

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tags

# Keep this list synchronized with ACM's CertificateKeyAlgorithm model so
# list_certificates does not omit certificates that use non-default key types.
CERTIFICATE_KEY_TYPES = [
    "RSA_1024",
    "RSA_2048",
    "RSA_3072",
    "RSA_4096",
    "EC_prime256v1",
    "EC_secp384r1",
    "EC_secp521r1",
]


def summary_can_match(summary, desired_names):
    """Return False when the list summary already rules a certificate out."""
    if summary.get("Type", "AMAZON_ISSUED") != "AMAZON_ISSUED" or summary.get("ManagedBy"):
        return False

    names = summary.get("SubjectAlternativeNameSummaries")
    if summary.get("HasAdditionalSubjectAlternativeNames") is False and isinstance(names, list):
        return {name.lower() for name in names if isinstance(name, str)} == desired_names

    return True


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "domain_name": {"required": True, "type": "str"},
            "idempotency_token": {"no_log": False, "type": "str"},
            "purge_tags": {"default": True, "type": "bool"},
            "subject_alternative_names": {"elements": "str", "type": "list"},
            "tags": {"aliases": ["resource_tags"], "type": "dict"},
        },
        supports_check_mode=True,
    )

    domain_name = module.params["domain_name"]
    normalized_domain_name = domain_name.lower()
    idempotency_token = module.params["idempotency_token"]
    purge_tags = module.params["purge_tags"]
    subject_alternative_names = list(
        dict.fromkeys(
            name.lower()
            for name in module.params["subject_alternative_names"] or []
            if name.lower() != normalized_domain_name
        )
    )
    tags = module.params["tags"]

    if idempotency_token is not None and not re.fullmatch(r"\w{1,32}", idempotency_token, flags=re.ASCII):
        module.fail_json(msg="ACM certificate request idempotency_token must be 1 to 32 ASCII word characters")

    if len(subject_alternative_names) > 99:
        module.fail_json(msg="subject_alternative_names must contain at most 99 additional entries")

    require_valid_tags(module, tags, 50)

    client = module.client("acm", retry_decorator=AWSRetry.jittered_backoff())

    request_parameters = ["DomainName", "IdempotencyToken", "ValidationMethod"]
    if subject_alternative_names:
        request_parameters.append("SubjectAlternativeNames")

    if tags:
        request_parameters.append("Tags")

    require_client_methods(
        module,
        client,
        "AWS Certificate Manager",
        {
            "list_certificates": (
                "CertificateStatuses",
                "Includes",
                "MaxItems",
                "NextToken",
            )
        },
    )

    desired_names = {normalized_domain_name}
    desired_names.update(subject_alternative_names)

    summaries = query_list(
        module,
        client,
        "list_certificates",
        "CertificateSummaryList",
        "Unable to list AWS Certificate Manager certificates",
        CertificateStatuses=["PENDING_VALIDATION", "ISSUED"],
        Includes={"keyTypes": CERTIFICATE_KEY_TYPES},
    )

    candidate_summaries = []
    for summary in summaries:
        if not isinstance(summary, dict):
            module.fail_json(msg="AWS Certificate Manager returned an invalid certificate summary")

        summary_domain_name = summary.get("DomainName")
        if not isinstance(summary_domain_name, str) or not summary_domain_name:
            module.fail_json(msg="AWS Certificate Manager returned an invalid certificate summary")

        if summary_domain_name.lower() != normalized_domain_name:
            continue

        certificate_arn = summary.get("CertificateArn")
        if not isinstance(certificate_arn, str) or not certificate_arn:
            module.fail_json(msg="AWS Certificate Manager returned an invalid matching certificate summary")

        # Only describe certificates the summary cannot rule out; the details are rechecked below.
        if summary_can_match(summary, desired_names):
            candidate_summaries.append(summary)

    if candidate_summaries:
        require_client_methods(
            module,
            client,
            "AWS Certificate Manager",
            {"describe_certificate": ("CertificateArn",)},
        )

    matched = None
    for summary in candidate_summaries:
        certificate_arn = summary["CertificateArn"]

        try:
            response = client.describe_certificate(
                CertificateArn=certificate_arn,
                aws_retry=True,
            )
        except is_boto3_error_code("ResourceNotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to describe AWS Certificate Manager certificate {certificate_arn}",
            )

        certificate = response.get("Certificate")
        if not isinstance(certificate, dict) or not certificate.get("Status"):
            module.fail_json(
                msg=f"AWS Certificate Manager did not return a status for certificate {certificate_arn}",
            )

        if certificate["Status"] not in {"PENDING_VALIDATION", "ISSUED"}:
            continue

        if certificate.get("Type") != "AMAZON_ISSUED" or certificate.get("ManagedBy"):
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

        # Older botocore releases drop ManagedBy, so service-managed certificates cannot be excluded.
        module.require_botocore_at_least("1.38.4", reason="to reuse an existing certificate")

        created_at = certificate.get("CreatedAt")
        if created_at is None:
            module.fail_json(
                msg=f"AWS Certificate Manager did not return a creation time for certificate {certificate_arn}",
            )

        if matched is None or created_at > matched["CreatedAt"]:
            matched = {
                "CertificateArn": certificate_arn,
                "CreatedAt": created_at,
            }

    created = matched is None

    if created:
        if module.check_mode:
            module.exit_json(changed=True)

        require_client_methods(
            module,
            client,
            "AWS Certificate Manager",
            {"request_certificate": tuple(request_parameters)},
        )

        if idempotency_token is None:
            token_data = {
                "domain_name": normalized_domain_name,
                "subject_alternative_names": sorted(subject_alternative_names),
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
            response = client.request_certificate(**request, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to request AWS Certificate Manager certificate {domain_name}",
            )

        certificate_arn = response.get("CertificateArn")
        if not certificate_arn:
            module.fail_json(
                changed=True,
                msg=f"AWS Certificate Manager did not return an ARN for certificate {domain_name}",
            )
    else:
        certificate_arn = matched["CertificateArn"]

    changed = created

    if not created and tags is not None:
        require_client_methods(
            module,
            client,
            "AWS Certificate Manager",
            {"list_tags_for_certificate": ("CertificateArn",)},
        )
        try:
            response = client.list_tags_for_certificate(
                CertificateArn=certificate_arn,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list tags for AWS Certificate Manager certificate {certificate_arn}",
            )

        current_tags = response.get("Tags", []) if isinstance(response, dict) else None
        if not isinstance(current_tags, list) or any(
            not isinstance(tag, dict)
            or not isinstance(tag.get("Key"), str)
            or not isinstance(tag.get("Value", ""), str)
            for tag in current_tags
        ):
            module.fail_json(msg=f"AWS Certificate Manager returned invalid tags for certificate {certificate_arn}")

        # ACM tags may omit Value, which is equivalent to an empty value.
        current_tags = {tag["Key"]: tag.get("Value", "") for tag in current_tags}

        tags_to_set, tag_keys_to_unset = compare_aws_tags(
            current_tags,
            tags,
            purge_tags=purge_tags,
        )

        changed = bool(tags_to_set or tag_keys_to_unset)

        tag_methods = {}
        if tag_keys_to_unset and not module.check_mode:
            tag_methods["remove_tags_from_certificate"] = ("CertificateArn", "Tags")

        if tags_to_set and not module.check_mode:
            tag_methods["add_tags_to_certificate"] = ("CertificateArn", "Tags")

        if tag_methods:
            require_client_methods(
                module,
                client,
                "AWS Certificate Manager",
                tag_methods,
            )

        if tag_keys_to_unset and not module.check_mode:
            try:
                client.remove_tags_from_certificate(
                    CertificateArn=certificate_arn,
                    Tags=[{"Key": key} for key in tag_keys_to_unset],
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to remove tags from AWS Certificate Manager certificate {certificate_arn}",
                )

        if tags_to_set and not module.check_mode:
            try:
                client.add_tags_to_certificate(
                    CertificateArn=certificate_arn,
                    Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    changed=bool(tag_keys_to_unset),
                    msg=f"Unable to tag AWS Certificate Manager certificate {certificate_arn}",
                )

    module.exit_json(
        changed=changed,
        certificate_arn=certificate_arn,
    )


if __name__ == "__main__":
    main()
