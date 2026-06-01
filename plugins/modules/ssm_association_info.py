#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association_info
short_description: Gather information about aws systems manager associations
description:
  - Gathers information about AWS Systems Manager associations.
author:
  - Taylor Kimball (@tkimball83)
options:
  filters:
    description:
      - A dict of filters to apply when listing Systems Manager associations.
      - Filter keys and values are passed to the Systems Manager
        C(ListAssociations) API as C(AssociationFilterList).
    type: dict
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about AWS Systems Manager associations
  linuxhq.aws.ssm_association_info:

- name: Gather information about Systems Manager associations using filters
  linuxhq.aws.ssm_association_info:
    filters:
      Name: AWS-RunShellScript
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


def main():
    module = AnsibleAWSModule(
        argument_spec={"filters": {"type": "dict"}},
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    request = {}
    if module.params["filters"]:
        request["AssociationFilterList"] = []
        for key, value in module.params["filters"].items():
            values = value if isinstance(value, list) else [value]
            for item in values:
                request["AssociationFilterList"].append(
                    {"key": key, "value": str(item)}
                )

    try:
        listed_associations = paginated_query_with_retries(
            client, "list_associations", **request
        ).get("Associations", [])
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS Systems Manager associations")

    associations = []
    for association in listed_associations:
        if association.get("Name") is not None:
            associations.append(association)

    normalized_associations = []
    for association in associations:
        association_id = association.get("AssociationId")

        if association_id:
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
                    msg=(
                        "Unable to list tags for AWS Systems Manager association "
                        f"{association_id}"
                    ),
                )

        normalized_associations.append(
            boto3_resource_to_ansible_dict(
                association,
                ignore_list=["TargetMaps"],
                transform_tags=True,
                force_tags=False,
            )
        )

    module.exit_json(
        changed=False,
        associations=normalized_associations,
    )


if __name__ == "__main__":
    main()
