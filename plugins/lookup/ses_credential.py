#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
lookup: ses_credential
author:
  - Taylor Kimball (@tkimball83)
short_description: Generate an AWS SES SMTP password from an IAM secret access key
description:
  - Generates an AWS Simple Email Service SMTP password from an IAM secret access key.
options:
  aws_secret_access_key:
    description:
      - The IAM secret access key to transform into an SMTP password.
    required: true
    type: str
  region:
    description:
      - The AWS region used when deriving the SMTP password.
    required: true
    type: str
notes:
  - AWS SES SMTP credentials are region-specific.
"""

EXAMPLES = r"""
- name: Generate SES SMTP password
  ansible.builtin.set_fact:
    ses_smtp_password:
      "{{ lookup('linuxhq.aws.ses_credential',
                 aws_secret_access_key=aws_secret_access_key,
                 region='us-east-1') }}"
"""

RETURN = r"""
_raw:
  description:
    - The derived AWS SES SMTP password.
"""

import base64
import hashlib
import hmac
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

DATE = "11111111"
MESSAGE = "SendRawEmail"
SERVICE = "ses"
TERMINAL = "aws4_request"
VERSION = 0x04


def get_smtp_password(secret_access_key, region):
    signature = sign(("AWS4" + secret_access_key).encode("utf-8"), DATE)
    signature = sign(signature, region)
    signature = sign(signature, SERVICE)
    signature = sign(signature, TERMINAL)
    signature = sign(signature, MESSAGE)
    return base64.b64encode(bytes([VERSION]) + signature).decode("utf-8")


def sign(key, message):
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        region = kwargs.get("region")
        secret_access_key = kwargs.get("aws_secret_access_key")

        if region is None:
            raise AnsibleError("ses_credential lookup requires region=")
        if secret_access_key is None:
            raise AnsibleError("ses_credential lookup requires aws_secret_access_key=")
        if terms:
            raise AnsibleError("ses_credential lookup does not accept positional terms")

        return [get_smtp_password(secret_access_key, region)]
