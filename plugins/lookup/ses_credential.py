# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
name: ses_credential
version_added: "1.9.0"
author:
  - Taylor Kimball (@tkimball83)
short_description: Generate an AWS SES SMTP password from an IAM secret access key
description:
  - Generates an AWS Simple Email Service SMTP password from an IAM secret access key.
options:
  aws_secret_access_key:
    description:
      - The IAM secret access key to transform into an SMTP password.
      - This must not contain whitespace.
    required: true
    type: str
  region:
    aliases:
      - aws_region
    description:
      - The AWS region used when deriving the SMTP password.
      - This must match the AWS region name format, for example V(us-east-1).
    required: true
    type: str
notes:
  - AWS SES SMTP credentials are region-specific.
  - The returned SMTP password is a credential; protect it with C(no_log)
    wherever it is stored or used.
"""

EXAMPLES = r"""
- name: Generate SES SMTP password
  ansible.builtin.set_fact:
    ses_smtp_password:
      "{{ lookup('linuxhq.aws.ses_credential',
                 aws_secret_access_key=aws_secret_access_key,
                 region='us-east-1') }}"
  no_log: true
"""

RETURN = r"""
_raw:
  description:
    - The derived AWS SES SMTP password.
  returned: always
  type: list
  elements: str
"""

import base64
import hashlib
import hmac
import re

from ansible.errors import AnsibleLookupError
from ansible.module_utils.common.text.converters import to_bytes, to_text
from ansible.plugins.lookup import LookupBase

DATE = "11111111"
MESSAGE = "SendRawEmail"
REGION_PATTERN = re.compile(r"[a-z]{2,4}(?:-[a-z]{1,15})+-[0-9]+")
SERVICE = "ses"
TERMINAL = "aws4_request"
VERSION = 0x04


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)

        region = self.get_option("region")
        secret_access_key = self.get_option("aws_secret_access_key")

        if not isinstance(region, str) or not region.strip():
            raise AnsibleLookupError("ses_credential lookup requires a non-empty region=")

        if not isinstance(secret_access_key, str) or not secret_access_key.strip():
            raise AnsibleLookupError("ses_credential lookup requires a non-empty aws_secret_access_key=")

        if terms:
            raise AnsibleLookupError("ses_credential lookup does not accept positional terms")

        region = region.strip()
        # A mistyped region still produces a password, which SES then rejects without saying why.
        if not REGION_PATTERN.fullmatch(region):
            raise AnsibleLookupError(f"ses_credential lookup requires a valid AWS region name, not {region!r}")

        # The key itself is never included in the message, because it is a secret.
        if any(character.isspace() for character in secret_access_key):
            raise AnsibleLookupError("ses_credential lookup requires an aws_secret_access_key without whitespace")

        signature = to_bytes("AWS4" + secret_access_key)
        for message in (DATE, region, SERVICE, TERMINAL, MESSAGE):
            signature = hmac.new(signature, to_bytes(message), hashlib.sha256).digest()

        return [to_text(base64.b64encode(bytes([VERSION]) + signature))]
