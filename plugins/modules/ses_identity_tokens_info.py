#!/usr/bin/python
# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_tokens_info
short_description: Gather aws simple email service identity tokens
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity": {"required": True, "type": "str"},
        },
        supports_check_mode=True,
    )
    identity = module.params["identity"]

    if "@" in identity:
        module.fail_json(msg="identity must be a domain name, not an email address")

    client = module.client("ses", retry_decorator=AWSRetry.jittered_backoff())

    if module.check_mode:
        module.exit_json(
            changed=False,
            dkim_tokens=[],
            identity=identity,
            verification_token=None,
        )

    try:
        dkim_tokens = client.verify_domain_dkim(Domain=identity, aws_retry=True).get(
            "DkimTokens", []
        )
        verification_token = client.verify_domain_identity(
            Domain=identity, aws_retry=True
        ).get("VerificationToken")
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to get AWS SES tokens for {identity}")

    module.exit_json(
        changed=False,
        dkim_tokens=dkim_tokens,
        identity=identity,
        verification_token=verification_token,
    )


if __name__ == "__main__":
    main()
