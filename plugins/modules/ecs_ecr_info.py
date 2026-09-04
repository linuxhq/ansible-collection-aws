#!/usr/bin/python
# Copyright: Ansible Project
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
  repository_names:
    description:
      - ECR repository names used to limit the result set.
      - An empty list is returned when any listed repository does not exist.
      - This must contain at most 100 unique entries.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only gathers information and does not modify AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


def validate_repositories(module, response):
    repositories = response.get("repositories") if isinstance(response, dict) else None
    if not isinstance(repositories, list):
        module.fail_json(msg="ECR returned invalid repositories")
    for repository in repositories:
        if (
            not isinstance(repository, dict)
            or not isinstance(repository.get("repositoryArn"), str)
            or not repository["repositoryArn"]
            or not isinstance(repository.get("repositoryName"), str)
            or not repository["repositoryName"]
        ):
            module.fail_json(msg="ECR returned invalid repositories")
    return repositories


def main():
    argument_spec = {
        "registry_id": {"type": "str"},
        "repository_names": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    registry_id = module.params["registry_id"]
    repository_names = list(dict.fromkeys(module.params["repository_names"] or []))

    if len(repository_names) > 100:
        module.fail_json(msg="repository_names must contain at most 100 unique entries")

    client = module.client("ecr", retry_decorator=AWSRetry.jittered_backoff())

    request = {}
    if registry_id:
        request["registryId"] = registry_id
    if repository_names:
        request["repositoryNames"] = repository_names

    require_client_methods(
        module,
        client,
        "ECR",
        {"describe_repositories": tuple(request) + ("maxResults", "nextToken")},
    )

    try:
        response = paginated_query_with_retries(
            client,
            "describe_repositories",
            **request,
        )
    except is_boto3_error_code("RepositoryNotFoundException"):
        repositories = []
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg="Unable to describe AWS ECR repositories")
    else:
        repositories = validate_repositories(module, response)

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
