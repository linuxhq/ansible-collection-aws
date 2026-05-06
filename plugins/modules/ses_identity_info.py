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
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_to_snake_dict,
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

    if requested_name is not None:
        details = aws_response(
            sesv2_client,
            module,
            "get_email_identity",
            ignore_error_codes="NotFoundException",
            ignored_error_result=None,
            EmailIdentity=requested_name,
        )
        identities = (
            [normalize_identity(requested_name, details)] if details is not None else []
        )
    else:
        identities = [
            normalize_identity(
                identity,
                aws_response(
                    sesv2_client,
                    module,
                    "get_email_identity",
                    EmailIdentity=identity,
                ),
            )
            for identity in aws_paginated_list(
                ses_client,
                module,
                "list_identities",
                "Identities",
            )
        ]

    module.exit_json(
        changed=False,
        identities=identities,
    )


if __name__ == "__main__":
    main()
