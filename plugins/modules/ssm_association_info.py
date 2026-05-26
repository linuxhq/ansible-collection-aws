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


def association_filter_list(filters):
    result = []
    for key, value in (filters or {}).items():
        values = value if isinstance(value, list) else [value]
        result.extend({"key": key, "value": str(item)} for item in values)
    return result


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
    module = AnsibleAWSModule(
        argument_spec={"filters": {"type": "dict"}},
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    request = {}
    if module.params["filters"]:
        request["AssociationFilterList"] = association_filter_list(
            module.params["filters"]
        )

    associations = [
        association
        for association in paginated_query_with_retries(
            client, "list_associations", **request
        ).get("Associations", [])
        if association.get("Name") is not None
    ]

    module.exit_json(
        changed=False,
        associations=[
            boto3_resource_to_ansible_dict(
                association_with_tags(client, module, association),
                ignore_list=["TargetMaps"],
                transform_tags=True,
                force_tags=False,
            )
            for association in associations
        ],
    )


if __name__ == "__main__":
    main()
