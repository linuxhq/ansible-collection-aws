#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ecs_ecr_info
version_added: 1.9.1
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_request_params,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.resources import (
    aws_resource_list_to_snake_dicts,
)


def main():
    argument_spec = {
        "name": {"type": "str"},
        "registry_id": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ecr")

    params = aws_request_params(
        {
            "registry_id": module.params["registry_id"] or None,
            "repository_names": (
                [module.params["name"]] if module.params["name"] is not None else None
            ),
        },
        capitalize_first=False,
    )

    module.exit_json(
        changed=False,
        repositories=aws_resource_list_to_snake_dicts(
            aws_paginated_list(
                client,
                module,
                "describe_repositories",
                "repositories",
                **params,
            )
        ),
    )


if __name__ == "__main__":
    main()
