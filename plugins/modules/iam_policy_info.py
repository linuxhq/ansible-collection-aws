#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_policy_info
short_description: Gather information about aws iam inline policies
description:
  - Gathers information about AWS IAM inline policies for users and groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  group_names:
    description:
      - IAM group names used to limit group inline policy results.
      - When omitted, all groups matching O(path_prefix) are queried.
    elements: str
    type: list
  path_prefix:
    description:
      - IAM path prefix used when listing users and groups.
    type: str
  policy_names:
    description:
      - IAM inline policy names used to limit returned policy documents.
      - Policy names are filtered after listing inline policies for each
        selected user or group.
    elements: str
    type: list
  user_names:
    description:
      - IAM user names used to limit user inline policy results.
      - When omitted, all users matching O(path_prefix) are queried.
    elements: str
    type: list
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about IAM inline policies
  linuxhq.aws.iam_policy_info:

- name: Gather information about inline policies for selected users
  linuxhq.aws.iam_policy_info:
    user_names:
      - molecule

- name: Gather information about inline policies below an IAM path
  linuxhq.aws.iam_policy_info:
    path_prefix: /service/
"""

RETURN = r"""
group_policies:
  description:
    - The IAM group inline policy information.
  returned: always
  type: list
  elements: dict
user_policies:
  description:
    - The IAM user inline policy information.
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
    scrub_none_parameters,
)


def build_entity_policies(client, module, entity_type, names):
    if entity_type == "Group":
        list_operation = "list_group_policies"
        get_operation = "get_group_policy"
    else:
        list_operation = "list_user_policies"
        get_operation = "get_user_policy"

    results = []

    for name in names:
        all_policy_names = paginated_query_with_retries(
            client,
            list_operation,
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {f"{entity_type.lower()}_name": name},
                    capitalize_first=True,
                )
            ),
        ).get("PolicyNames", [])
        policy_names = [
            policy_name
            for policy_name in all_policy_names
            if not module.params["policy_names"]
            or policy_name in module.params["policy_names"]
        ]
        results.append(
            {
                "name": name,
                "all_policy_names": all_policy_names,
                "policies": [
                    {
                        "policy_name": policy_name,
                        "policy_document": getattr(client, get_operation)(
                            **scrub_none_parameters(
                                snake_dict_to_camel_dict(
                                    {
                                        f"{entity_type.lower()}_name": name,
                                        "policy_name": policy_name,
                                    },
                                    capitalize_first=True,
                                )
                            ),
                            aws_retry=True,
                        ).get("PolicyDocument"),
                    }
                    for policy_name in policy_names
                ],
                "policy_names": policy_names,
            }
        )

    return results


def entity_names(client, module, entity_type):
    explicit_names = module.params[f"{entity_type.lower()}_names"]
    if explicit_names:
        return explicit_names
    response_key = f"{entity_type}s"
    name_key = f"{entity_type}Name"
    return [
        entity[name_key]
        for entity in paginated_query_with_retries(
            client,
            f"list_{entity_type.lower()}s",
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {"path_prefix": module.params["path_prefix"]},
                    capitalize_first=True,
                )
            ),
        ).get(response_key, [])
        if entity.get(name_key)
    ]


def main():
    argument_spec = {
        "group_names": {"elements": "str", "type": "list"},
        "path_prefix": {"type": "str"},
        "policy_names": {"elements": "str", "type": "list"},
        "user_names": {"elements": "str", "type": "list"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )
    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())
    group_names = entity_names(client, module, "Group")
    user_names = entity_names(client, module, "User")

    module.exit_json(
        changed=False,
        group_policies=build_entity_policies(
            client,
            module,
            "Group",
            group_names,
        ),
        user_policies=build_entity_policies(
            client,
            module,
            "User",
            user_names,
        ),
    )


if __name__ == "__main__":
    main()
