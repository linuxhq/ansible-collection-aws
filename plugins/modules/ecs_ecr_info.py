#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ecs_ecr_info
version_added: "1.9.0"
short_description: Gather information about AWS Elastic Container Registry repositories
description:
  - Gather information about AWS Elastic Container Registry repositories.
author:
  - Taylor Kimball (@tkimball83)
options:
  registry_id:
    description:
      - The AWS account ID associated with the registry to describe.
    type: str
  name:
    description:
      - Optional repository name to limit the result set.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about ECR repositories
  linuxhq.aws.ecs_ecr_info:

- name: Gather information about selected ECR repositories
  linuxhq.aws.ecs_ecr_info:
    name: my-repository
"""

RETURN = r"""
repositories:
  description:
    - A list of AWS Elastic Container Registry repositories.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    scrub_none_parameters,
)


def main():
    argument_spec = {
        "name": {"type": "str"},
        "registry_id": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ecr", retry_decorator=AWSRetry.jittered_backoff())

    params = scrub_none_parameters(
        snake_dict_to_camel_dict(
            {
                "registry_id": module.params["registry_id"] or None,
                "repository_names": (
                    [module.params["name"]]
                    if module.params["name"] is not None
                    else None
                ),
            },
            capitalize_first=False,
        )
    )

    module.exit_json(
        changed=False,
        repositories=boto3_resource_list_to_ansible_dict(
            paginated_query_with_retries(
                client,
                "describe_repositories",
                **params,
            ).get("repositories", []),
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
