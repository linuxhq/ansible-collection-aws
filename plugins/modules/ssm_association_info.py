#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association_info
version_added: "1.9.5"
short_description: Gather information about AWS Systems Manager associations
description:
  - Gathers information about AWS Systems Manager associations.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about AWS Systems Manager associations
  linuxhq.aws.ssm_association_info:
"""

RETURN = r"""
associations:
  description:
    - A list of AWS Systems Manager associations.
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

SSM_ASSOCIATION_RESOURCE_TYPE = "Association"


def association_with_tags(client, module, association):
    association_id = association.get("AssociationId")
    if not association_id:
        return association
    association = dict(association)
    try:
        association["Tags"] = client.list_tags_for_resource(
            ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
            ResourceId=association_id,
            aws_retry=True,
        ).get("TagList", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list tags for AWS Systems Manager association {association_id}",
        )
    return association


def main():
    module = AnsibleAWSModule(argument_spec={}, supports_check_mode=True)
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    associations = [
        association
        for association in paginated_query_with_retries(
            client, "list_associations"
        ).get("Associations", [])
        if association.get("Name") is not None
    ]

    module.exit_json(
        changed=False,
        associations=[
            boto3_resource_to_ansible_dict(
                association,
                ignore_list=["TargetMaps"],
                transform_tags=True,
                force_tags=False,
            )
            for association in [
                association_with_tags(client, module, association)
                for association in associations
            ]
        ],
    )


if __name__ == "__main__":
    main()
