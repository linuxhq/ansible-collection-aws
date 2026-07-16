#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - Mutually exclusive with O(name).
    choices:
      - Domain
      - EmailAddress
    type: str
  name:
    description:
      - SES identity name used to limit the result set.
      - An identity that does not exist results in an empty list.
      - Mutually exclusive with O(identity_type).
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
    - Each identity includes C(name) added by the module.
    - C(identity_type) uses the SES v2 format, for example V(DOMAIN) or
      V(EMAIL_ADDRESS), which differs from the O(identity_type) option
      values.
    - C(policies) keys are returned as provided by the SES API.
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
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "identity_type": {"choices": ["Domain", "EmailAddress"], "type": "str"},
            "name": {"type": "str"},
        },
        mutually_exclusive=[["identity_type", "name"]],
        supports_check_mode=True,
    )
    ses_client = module.client("ses", retry_decorator=AWSRetry.jittered_backoff())
    sesv2_client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        ses_client,
        "SES",
        {"list_identities": ("IdentityType",)},
    )
    require_client_methods(
        module,
        sesv2_client,
        "SESv2",
        {"get_email_identity": ("EmailIdentity",)},
    )

    identity_type = module.params["identity_type"]
    name = module.params["name"]
    identities = []

    if name:
        identity_names = [name]
    else:
        request = {}
        if identity_type is not None:
            request["IdentityType"] = identity_type

        try:
            identity_names = paginated_query_with_retries(
                ses_client,
                "list_identities",
                **request,
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
            continue
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS SES identity {identity_name}",
            )

        details.pop("ResponseMetadata", None)
        identity = boto3_resource_to_ansible_dict(
            details,
            transform_tags=True,
            force_tags=False,
            ignore_list=["Policies"],
        )

        identity["name"] = identity_name
        identities.append(identity)

    module.exit_json(
        changed=False,
        identities=identities,
    )


if __name__ == "__main__":
    main()
