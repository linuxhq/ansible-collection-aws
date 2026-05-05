#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_info
version_added: 1.9.1
short_description: Gather information about AWS SES identities
description:
  - Gathers information about AWS SES identities.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The SES identity to query.
      - When omitted, all identities are returned.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about SES identities
  linuxhq.aws.ses_identity_info:

- name: Gather information about a single SES identity
  linuxhq.aws.ses_identity_info:
    name: molecule.org
"""

RETURN = r"""
identities:
  description:
    - The SES identities.
  returned: always
  type: list
  elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_to_snake_dict,
)


def get_email_identity(client, module, identity):
    return aws_response(
        client,
        module,
        "get_email_identity",
        EmailIdentity=identity,
    )


def list_identities(client, module):
    return aws_paginated_list(
        client,
        module,
        "list_identities",
        "Identities",
    )


def normalize_identity(identity, details):
    normalized = aws_resource_to_snake_dict(details)
    normalized["name"] = identity
    return normalized


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    ses_client = module.client("ses")
    sesv2_client = module.client("sesv2")
    requested_name = module.params["name"]

    identities = list_identities(ses_client, module)
    if requested_name is not None:
        identities = [identity for identity in identities if identity == requested_name]

    module.exit_json(
        changed=False,
        identities=[
            normalize_identity(
                identity,
                get_email_identity(sesv2_client, module, identity),
            )
            for identity in identities
        ],
    )


if __name__ == "__main__":
    main()
