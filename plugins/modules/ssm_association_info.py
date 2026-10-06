#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_association_info
version_added: '1.9.0'
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
    association_name:
      description: Association name.
      returned: when configured
      type: str
    association_version:
      description: Association version.
      returned: when available
      type: str
    document_version:
      description: The document version the association uses.
      returned: when available
      type: str
    duration:
      description: The number of hours the association can run on its targets.
      returned: when configured
      type: int
    instance_id:
      description: The managed node ID.
      returned: when available
      type: str
    last_execution_date:
      description: The date the association last ran.
      returned: when available
      type: str
    name:
      description: SSM document name.
      returned: always
      type: str
    overview:
      description: The association status overview.
      returned: when available
      type: dict
      contains:
        association_status_aggregated_count:
          description:
            - Number of targets in each association status.
            - Status names, such as C(Success) and C(Failed), are returned as
              AWS returns them.
          returned: when available
          type: dict
        detailed_status:
          description: Detailed association status.
          returned: when available
          type: str
        status:
          description: Association status.
          returned: when available
          type: str
    schedule_expression:
      description: Association schedule expression.
      returned: when configured
      type: str
    schedule_offset:
      description: The number of days to wait after the scheduled day to run the association.
      returned: when configured
      type: int
    tags:
      description: Association tags.
      returned: always
      type: dict
    targets:
      description:
        - Association targets.
        - Each target also contains C(values), the list of target value
          strings; read it as C(target["values"]) because Jinja dot notation
          cannot access a key named C(values).
      returned: when configured
      type: list
      elements: dict
      contains:
        key:
          description: Target key.
          returned: always
          type: str
    target_maps:
      description:
        - Mappings of document parameters to target resources.
        - Parameter names and target values are returned as AWS returns them.
      returned: when configured
      type: list
      elements: dict
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    SSM_ASSOCIATION_RESOURCE_TYPE,
    association_overview,
    list_ssm_tags,
    ssm_filter_list,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={"filters": {"type": "dict"}},
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())

    filters = module.params["filters"]
    request = {}
    if filters:
        request["AssociationFilterList"] = ssm_filter_list(filters, "key", "value", split_values=True)

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

        tags = list_ssm_tags(
            module,
            client,
            SSM_ASSOCIATION_RESOURCE_TYPE,
            association_id,
            "AWS Systems Manager association",
            missing_ok=True,
        )
        if tags is None:
            continue

        normalized_associations.append(
            boto3_resource_to_ansible_dict(
                dict(association, Tags=tags),
                ignore_list=["TargetMaps"],
                transform_tags=True,
                force_tags=False,
                nested_transforms={"Overview": association_overview},
            )
        )

    module.exit_json(
        changed=False,
        associations=normalized_associations,
    )


if __name__ == "__main__":
    main()
