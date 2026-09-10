#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association_info
short_description: Gather information about AWS Systems Manager associations
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
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
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
    - Each association includes C(tags) gathered by the module.
  returned: always
  type: list
  elements: dict
  contains:
    association_id:
      description: Association identifier.
      returned: always
      type: str
    name:
      description: SSM document name.
      returned: always
      type: str
    schedule_expression:
      description: Association schedule expression.
      returned: when configured
      type: str
    tags:
      description: Association tags.
      returned: always
      type: dict
    targets:
      description: Association targets.
      returned: when configured
      type: list
      elements: dict
      contains:
        key:
          description: Target key.
          returned: always
          type: str
"""

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)

SSM_ASSOCIATION_RESOURCE_TYPE = "Association"


def main():
    module = AnsibleAWSModule(
        argument_spec={"filters": {"type": "dict"}},
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    filters = module.params["filters"]
    request = {}
    if filters:
        request["AssociationFilterList"] = []
        for key, value in filters.items():
            values = value if isinstance(value, list) else [value]

            for item in values:
                request["AssociationFilterList"].append({"key": key, "value": str(item)})

    require_client_methods(
        module,
        client,
        "Systems Manager",
        {
            "list_associations": tuple(request),
            "list_tags_for_resource": ("ResourceId", "ResourceType"),
        },
    )

    associations = query_list(
        module,
        client,
        "list_associations",
        "Associations",
        "Unable to list AWS Systems Manager associations",
        **request,
    )

    normalized_associations = []
    for association in associations:
        if not isinstance(association, dict):
            module.fail_json(msg="Unexpected response while listing AWS Systems Manager associations")

        association_id = association.get("AssociationId")

        if not isinstance(association_id, str) or not association_id:
            module.fail_json(msg="Unexpected response while listing AWS Systems Manager associations")

        association = dict(association)

        try:
            response = client.list_tags_for_resource(
                ResourceType=SSM_ASSOCIATION_RESOURCE_TYPE,
                ResourceId=association_id,
                aws_retry=True,
            )
        except is_boto3_error_code("InvalidResourceId"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=("Unable to list tags for AWS Systems Manager association " f"{association_id}"),
            )

        tags = response.get("TagList", []) if isinstance(response, dict) else None
        if not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags):
            module.fail_json(msg=f"Unexpected response while listing tags for association {association_id}")

        association["Tags"] = tags

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
