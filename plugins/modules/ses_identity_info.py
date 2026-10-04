#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_info
version_added: '1.9.0'
short_description: Gather information about AWS Simple Email Service identities
description:
  - Gathers information about AWS SES identities, including their DKIM tokens
    and verification status, without modifying them.
author:
  - Taylor Kimball (@tkimball83)
options:
  identity_type:
    description:
      - Optional SES identity type used to limit the result set when O(name) is omitted.
      - Mutually exclusive with O(name).
    choices:
      - Domain
      - EmailAddress
    type: str
  name:
    description:
      - SES identity name used to limit the result set.
      - This must not be empty when provided.
      - An identity that does not exist results in an empty list.
      - Mutually exclusive with O(identity_type).
    type: str
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
- name: Gather information about SES identities
  linuxhq.aws.ses_identity_info:

- name: Gather information about a single SES identity
  linuxhq.aws.ses_identity_info:
    name: molecule.org

- name: Gather information about SES domain identities
  linuxhq.aws.ses_identity_info:
    identity_type: Domain
"""

RETURN = r"""
identities:
  description:
    - The SES identities.
    - Each identity includes C(name) added by the module.
    - C(identity_type) uses the SES v2 format, for example V(DOMAIN) or
      V(EMAIL_ADDRESS), which differs from the O(identity_type) option
      values.
    - C(policies) keys are returned as provided by the SES API.
  returned: always
  type: list
  elements: dict
  contains:
    dkim_attributes:
      description: The identity's DKIM settings.
      returned: when available
      type: dict
      contains:
        signing_attributes_origin:
          description: Whether DKIM uses Easy DKIM (C(AWS_SES)) or keys you supply.
          returned: when available
          type: str
        signing_enabled:
          description: Whether DKIM signing is enabled.
          returned: when available
          type: bool
        status:
          description: The DKIM verification status.
          returned: when available
          type: str
        tokens:
          description: The Easy DKIM tokens for the identity's DKIM CNAME records.
          returned: when available
          type: list
          elements: str
    name:
      description: The SES identity name.
      returned: always
      type: str
    verification_status:
      description: The identity's verification status.
      returned: when available
      type: str
    verification_token:
      description:
        - The SES v1 domain verification token for the C(_amazonses) TXT
          record, the alternative to DKIM verification.
      returned: when AWS returns it for a domain identity
      type: str
    verified_for_sending_status:
      description: Whether the identity can be used to send email.
      returned: when available
      type: bool
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.iterators import chunks
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_identity_names(module, identity_names):
    if not isinstance(identity_names, list) or any(
        not isinstance(identity_name, str) or not identity_name for identity_name in identity_names
    ):
        module.fail_json(msg="AWS SES returned an invalid identity name")


def validate_identity_details(module, details, identity_name):
    if not isinstance(details, dict):
        module.fail_json(msg=f"AWS SES returned invalid details for identity {identity_name}")

    tags = details.get("Tags", [])
    if not isinstance(tags, list) or any(
        not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str)
        for tag in tags
    ):
        module.fail_json(msg=f"AWS SES returned invalid tags for identity {identity_name}")

    policies = details.get("Policies", {})
    if not isinstance(policies, dict):
        module.fail_json(msg=f"AWS SES returned invalid policies for identity {identity_name}")


def get_verification_tokens(module, ses_client, identity_names):
    """Return the SES v1 domain verification tokens, keyed by identity name."""
    tokens = {}
    # GetIdentityVerificationAttributes accepts up to 100 identities per request.
    for batch in chunks(identity_names, 100):
        try:
            response = ses_client.get_identity_verification_attributes(Identities=batch, aws_retry=True)
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg="Unable to get AWS SES identity verification attributes")

        attributes = response.get("VerificationAttributes", {}) if isinstance(response, dict) else None
        if not isinstance(attributes, dict) or any(not isinstance(value, dict) for value in attributes.values()):
            module.fail_json(msg="AWS SES returned invalid identity verification attributes")

        for identity_name, value in attributes.items():
            if isinstance(value.get("VerificationToken"), str):
                tokens[identity_name] = value["VerificationToken"]

    return tokens


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity_type": {"choices": ["Domain", "EmailAddress"], "type": "str"},
            "name": {"type": "str"},
        },
        mutually_exclusive=[["identity_type", "name"]],
        supports_check_mode=True,
    )
    identity_type = module.params["identity_type"]
    name = module.params["name"]

    if name == "":
        module.fail_json(msg="name must not be empty")

    ses_client = module.client("ses", retry_decorator=AWSRetry.jittered_backoff())
    ses_methods = {"get_identity_verification_attributes": ("Identities",)}
    if name is None:
        ses_methods["list_identities"] = ("IdentityType", "MaxItems", "NextToken")

    require_client_methods(module, ses_client, "SES", ses_methods)

    sesv2_client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(
        module,
        sesv2_client,
        "SESv2",
        {"get_email_identity": ("EmailIdentity",)},
    )

    identities = []

    if name is not None:
        identity_names = [name]
    else:
        request = {}
        if identity_type is not None:
            request["IdentityType"] = identity_type

        identity_names = query_list(
            module,
            ses_client,
            "list_identities",
            "Identities",
            "Unable to list AWS SES identities",
            **request,
        )

    validate_identity_names(module, identity_names)

    for identity_name in identity_names:
        try:
            details = sesv2_client.get_email_identity(
                EmailIdentity=identity_name,
                aws_retry=True,
            )
        except is_boto3_error_code("NotFoundException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS SES identity {identity_name}",
            )

        validate_identity_details(module, details, identity_name)
        details = details.copy()
        details.pop("ResponseMetadata", None)
        identity = boto3_resource_to_ansible_dict(
            details,
            transform_tags=True,
            force_tags=False,
            ignore_list=["Policies"],
        )

        identity["name"] = identity_name
        identities.append(identity)

    if identities:
        verification_tokens = get_verification_tokens(module, ses_client, [identity["name"] for identity in identities])
        for identity in identities:
            if identity["name"] in verification_tokens:
                identity["verification_token"] = verification_tokens[identity["name"]]

    module.exit_json(
        changed=False,
        identities=identities,
    )


if __name__ == "__main__":
    main()
