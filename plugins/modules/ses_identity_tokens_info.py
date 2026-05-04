#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_tokens_info
version_added: 1.9.1
short_description: Gather AWS SES domain identity tokens
description:
  - Gathers AWS SES DKIM and verification tokens for a domain identity.
author:
  - Taylor Kimball (@tkimball83)
options:
  identity:
    description:
      - The SES domain identity.
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


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity": {"required": True, "type": "str"},
        },
        supports_check_mode=True,
    )
    client = module.client("ses")
    identity = module.params["identity"]

    try:
        dkim_response = client.verify_domain_dkim(Domain=identity)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to gather AWS SES DKIM tokens for {identity}",
        )

    try:
        verification_response = client.verify_domain_identity(Domain=identity)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to gather AWS SES verification token for {identity}",
        )

    module.exit_json(
        changed=False,
        dkim_tokens=dkim_response.get("DkimTokens", []),
        identity=identity,
        verification_token=verification_response.get("VerificationToken"),
    )


if __name__ == "__main__":
    main()
