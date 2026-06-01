#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_info
short_description: Gather information about aws simple email service identities
description:
  - Gathers information about AWS SES identities.
author:
  - Taylor Kimball (@tkimball83)
options:
  identity_type:
    description:
      - Optional SES identity type used to limit the result set when O(name) is omitted.
    choices:
      - Domain
      - EmailAddress
    type: str
  name:
    description:
      - SES identity name used to limit the result set.
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

- name: Gather information about SES domain identities
  linuxhq.aws.ses_identity_info:
    identity_type: Domain
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
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity_type": {"choices": ["Domain", "EmailAddress"], "type": "str"},
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    ses_client = module.client("ses", retry_decorator=AWSRetry.jittered_backoff())
    sesv2_client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())
    identities = []

    if module.params["name"]:
        identity_names = [module.params["name"]]
    else:
        list_kwargs = {}
        if module.params["identity_type"] is not None:
            list_kwargs["IdentityType"] = module.params["identity_type"]

        try:
            identity_names = paginated_query_with_retries(
                ses_client,
                "list_identities",
                **list_kwargs,
            ).get("Identities", [])
        except Exception as e:
            module.fail_json_aws(e, msg="Unable to list AWS SES identities")

    for identity_name in identity_names:
        try:
            details = sesv2_client.get_email_identity(
                EmailIdentity=identity_name,
                aws_retry=True,
            )
        except is_boto3_error_code("NotFoundException"):
            details = None
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS SES identity {identity_name}",
            )

        if details is not None:
            identity = boto3_resource_to_ansible_dict(
                details, transform_tags=False, force_tags=False
            )

            identity["name"] = identity_name
            identities.append(identity)

    module.exit_json(
        changed=False,
        identities=identities,
    )


if __name__ == "__main__":
    main()
