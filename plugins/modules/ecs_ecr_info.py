#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ecs_ecr_info
short_description: Gather information about aws elastic container registry repositories
description:
  - Gather information about AWS Elastic Container Registry repositories.
author:
  - Taylor Kimball (@tkimball83)
options:
  repository_names:
    description:
      - ECR repository names used to limit the result set.
    elements: str
    type: list
  registry_id:
    description:
      - The AWS account ID associated with the registry to describe.
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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)


def main():
    argument_spec = {
        "repository_names": {"elements": "str", "type": "list"},
        "registry_id": {"type": "str"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    client = module.client("ecr", retry_decorator=AWSRetry.jittered_backoff())

    params = {}
    if module.params["registry_id"]:
        params["registryId"] = module.params["registry_id"]
    if module.params["repository_names"]:
        params["repositoryNames"] = module.params["repository_names"]

    try:
        repositories = paginated_query_with_retries(
            client,
            "describe_repositories",
            **params,
        ).get("repositories", [])
    except is_boto3_error_code("RepositoryNotFoundException"):
        repositories = []
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe AWS ECR repositories")

    module.exit_json(
        changed=False,
        repositories=boto3_resource_list_to_ansible_dict(
            repositories,
            transform_tags=False,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
