#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_dkim
version_added: '2.6.0'
short_description: Manage Easy DKIM for an AWS Simple Email Service domain identity
description:
  - Manages Easy DKIM for an AWS SES domain identity.
  - With O(signing_enabled=true), Easy DKIM tokens are generated when the
    identity has none, or when it uses DKIM keys you supplied, and DKIM
    signing is enabled.
  - Publishing the returned tokens as DKIM CNAME records verifies the domain.
  - The identity must already exist.
author:
  - Taylor Kimball (@tkimball83)
options:
  identity:
    description:
      - The SES domain identity.
      - This must be a domain name; DKIM is configured on domains, not email
        addresses.
    required: true
    type: str
  signing_enabled:
    description:
      - Whether DKIM signing is enabled for the identity.
      - V(false) disables signing and keeps the existing DKIM tokens.
    default: true
    type: bool
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: The module reports the DKIM settings that would result from the requested changes.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Ensure Easy DKIM is enabled for an SES domain identity
  linuxhq.aws.ses_identity_dkim:
    identity: example.com
  register: dkim

- name: Ensure DKIM signing is disabled for an SES domain identity
  linuxhq.aws.ses_identity_dkim:
    identity: example.com
    signing_enabled: false
"""

RETURN = r"""
dkim_attributes:
  description:
    - The identity's DKIM settings after module execution.
    - In check mode, newly generated tokens are not yet known and are empty.
  returned: always
  type: dict
  contains:
    current_signing_key_length:
      description: The key length of the DKIM key pair currently in use, such as V(RSA_2048_BIT).
      returned: when available
      type: str
    last_key_generation_timestamp:
      description: When the DKIM key pair was last generated, in ISO 8601 format.
      returned: when available
      type: str
    next_signing_key_length:
      description: The key length of the next DKIM key pair to be generated, such as V(RSA_2048_BIT).
      returned: when available
      type: str
    signing_attributes_origin:
      description:
        - How the DKIM keys were provided.
        - V(AWS_SES) and the regional C(AWS_SES_<REGION>) values, such as
          V(AWS_SES_US_EAST_1), indicate Easy DKIM; V(EXTERNAL) indicates keys
          you supply.
      returned: when available
      type: str
    signing_enabled:
      description: Whether DKIM signing is enabled.
      returned: when available
      type: bool
    signing_hosted_zone:
      description: The hosted zone where SES publishes the DKIM public key.
      returned: when available
      type: str
    status:
      description: The DKIM verification status.
      returned: when available
      type: str
    tokens:
      description: The Easy DKIM tokens for the identity's DKIM CNAME records.
      returned: when available
      type: list
      elements: str
identity:
  description: The SES domain identity.
  returned: always
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
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def get_dkim_attributes(client, module):
    identity = module.params["identity"]

    try:
        response = client.get_email_identity(EmailIdentity=identity, aws_retry=True)
    except is_boto3_error_code("NotFoundException"):
        module.fail_json(msg=f"AWS SES identity {identity} does not exist")
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS SES identity {identity}")

    attributes = response.get("DkimAttributes", {}) if isinstance(response, dict) else None
    if not isinstance(attributes, dict):
        module.fail_json(msg=f"AWS SES returned invalid DKIM attributes for identity {identity}")

    return attributes


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity": {"required": True, "type": "str"},
            "signing_enabled": {"default": True, "type": "bool"},
        },
        supports_check_mode=True,
    )
    identity = module.params["identity"]
    signing_enabled = module.params["signing_enabled"]

    if not identity:
        module.fail_json(msg="identity must not be empty")

    if "@" in identity:
        module.fail_json(msg="identity must be a domain name, not an email address")

    client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(
        module,
        client,
        "SESv2",
        {
            "get_email_identity": ("EmailIdentity",),
            "put_email_identity_dkim_attributes": ("EmailIdentity", "SigningEnabled"),
            "put_email_identity_dkim_signing_attributes": ("EmailIdentity", "SigningAttributesOrigin"),
        },
    )

    current = get_dkim_attributes(client, module)
    # Easy DKIM tokens exist only once AWS has generated them; AWS_SES and the
    # regional AWS_SES_<REGION> origins (deterministic Easy DKIM) are all Easy DKIM.
    origin = current.get("SigningAttributesOrigin")
    easy_dkim = isinstance(origin, str) and origin.startswith("AWS_SES")
    generate_tokens = signing_enabled and not (easy_dkim and current.get("Tokens"))
    changed = generate_tokens or bool(current.get("SigningEnabled")) != signing_enabled

    if changed and module.check_mode:
        current = dict(current, SigningEnabled=signing_enabled)
        if generate_tokens:
            current.update(SigningAttributesOrigin="AWS_SES", Tokens=[])
    elif changed:
        if generate_tokens:
            try:
                client.put_email_identity_dkim_signing_attributes(
                    EmailIdentity=identity,
                    SigningAttributesOrigin="AWS_SES",
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to generate Easy DKIM tokens for AWS SES identity {identity}")

            current = get_dkim_attributes(client, module)

        if bool(current.get("SigningEnabled")) != signing_enabled:
            try:
                client.put_email_identity_dkim_attributes(
                    EmailIdentity=identity,
                    SigningEnabled=signing_enabled,
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, msg=f"Unable to update DKIM signing for AWS SES identity {identity}")

            current = get_dkim_attributes(client, module)

    module.exit_json(
        changed=changed,
        dkim_attributes=boto3_resource_to_ansible_dict(current, transform_tags=False, force_tags=False),
        identity=identity,
    )


if __name__ == "__main__":
    main()
