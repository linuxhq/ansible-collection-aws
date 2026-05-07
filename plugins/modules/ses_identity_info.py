#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ses_identity_info
version_added: "1.9.0"
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

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"type": "str"},
        },
        supports_check_mode=True,
    )
    ses_client = module.client("ses", retry_decorator=AWSRetry.jittered_backoff())
    sesv2_client = module.client("sesv2", retry_decorator=AWSRetry.jittered_backoff())
    requested_name = module.params["name"]

    if requested_name is not None:
        try:
            details = sesv2_client.get_email_identity(
                **scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {"email_identity": requested_name},
                        capitalize_first=True,
                    )
                ),
                aws_retry=True,
            )
        except is_boto3_error_code("NotFoundException"):
            details = None
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS SES identity {requested_name}",
            )
        identities = []
        if details is not None:
            identity = boto3_resource_to_ansible_dict(
                details, transform_tags=False, force_tags=False
            )
            identity["name"] = requested_name
            identities.append(identity)
    else:
        identities = []
        for identity_name in paginated_query_with_retries(
            ses_client,
            "list_identities",
        ).get("Identities", []):
            identity = boto3_resource_to_ansible_dict(
                sesv2_client.get_email_identity(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {"email_identity": identity_name},
                            capitalize_first=True,
                        )
                    ),
                    aws_retry=True,
                ),
                transform_tags=False,
                force_tags=False,
            )
            identity["name"] = identity_name
            identities.append(identity)

    module.exit_json(
        changed=False,
        identities=identities,
    )


if __name__ == "__main__":
    main()
