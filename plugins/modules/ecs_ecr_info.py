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
  repository_names:
    description:
      - Optional list of repository names to limit the result set.
    type: list
    elements: str
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
    repository_names:
      - my-repository
"""

RETURN = r"""
repositories:
  description:
    - A list of AWS Elastic Container Registry repositories.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def main():
    argument_spec = {
        "registry_id": {"type": "str"},
        "repository_names": {"type": "list", "elements": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ecr")

    params = {}
    if module.params["registry_id"]:
        params["registryId"] = module.params["registry_id"]
    if module.params["repository_names"]:
        params["repositoryNames"] = module.params["repository_names"]

    repositories = []
    next_token = None

    try:
        while True:
            request = dict(params)
            if next_token:
                request["nextToken"] = next_token
            response = client.describe_repositories(**request)
            repositories.extend(response.get("repositories", []))
            next_token = response.get("nextToken")
            if not next_token:
                break
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to describe AWS Elastic Container Registry repositories"
        )

    module.exit_json(
        changed=False,
        repositories=[
            camel_dict_to_snake_dict(repository) for repository in repositories
        ],
    )


if __name__ == "__main__":
    main()
