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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_email_identity(client, module, identity):
    get_email_identity = AWSRetry.jittered_backoff()(client.get_email_identity)
    try:
        return get_email_identity(EmailIdentity=identity)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS SES identity {identity}",
        )


def list_identities(client, module):
    try:
        response = paginated_query_with_retries(client, "list_identities")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS SES identities",
        )
    return response.get("Identities", [])


def normalize_identity(identity, details):
    normalized = boto3_resource_to_ansible_dict(details, force_tags=False)
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
