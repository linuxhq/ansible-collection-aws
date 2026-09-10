#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_tokens_info
short_description: Gather AWS Simple Email Service identity tokens
description:
  - Gathers AWS SES DKIM and verification tokens for a domain identity.
  - Requests the tokens by initiating domain verification, so the identity
    does not need to exist yet and DNS records can be created first.
author:
  - Taylor Kimball (@tkimball83)
options:
  identity:
    description:
      - The SES domain identity.
      - This must be a domain name; email address identities do not have
        domain verification tokens.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: Does not initiate verification and returns empty token values.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Gather SES tokens for a domain identity
  linuxhq.aws.ses_identity_tokens_info:
    identity: molecule.org
"""

RETURN = r"""
dkim_tokens:
  description:
    - The SES DKIM tokens for the identity.
  returned: always
  type: list
  elements: str
identity:
  description:
    - The requested SES identity.
  returned: always
  type: str
verification_token:
  description:
    - The SES verification token for the identity.
  returned: always
  type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def domain_tokens_from_responses(module, dkim_response, verification_response, identity):
    if not isinstance(dkim_response, dict) or not isinstance(verification_response, dict):
        module.fail_json(msg=f"AWS SES returned invalid domain token responses for {identity}")

    dkim_tokens = dkim_response.get("DkimTokens", [])
    verification_token = verification_response.get("VerificationToken")
    if (
        not isinstance(dkim_tokens, list)
        or not dkim_tokens
        or any(not isinstance(token, str) or not token for token in dkim_tokens)
        or not isinstance(verification_token, str)
        or not verification_token
    ):
        module.fail_json(msg=f"AWS SES did not return domain tokens for {identity}")

    return dkim_tokens, verification_token


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity": {"required": True, "type": "str"},
        },
        supports_check_mode=True,
    )
    identity = module.params["identity"]

    if not identity:
        module.fail_json(msg="identity must not be empty")

    if "@" in identity:
        module.fail_json(msg="identity must be a domain name, not an email address")

    if module.check_mode:
        module.exit_json(
            changed=False,
            dkim_tokens=[],
            identity=identity,
            verification_token=None,
        )

    client = module.client("ses", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "SES",
        {
            "verify_domain_dkim": ("Domain",),
            "verify_domain_identity": ("Domain",),
        },
    )

    try:
        dkim_response = client.verify_domain_dkim(Domain=identity, aws_retry=True)
        verification_response = client.verify_domain_identity(Domain=identity, aws_retry=True)
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS SES tokens for {identity}")

    dkim_tokens, verification_token = domain_tokens_from_responses(
        module,
        dkim_response,
        verification_response,
        identity,
    )

    module.exit_json(
        changed=False,
        dkim_tokens=dkim_tokens,
        identity=identity,
        verification_token=verification_token,
    )


if __name__ == "__main__":
    main()
