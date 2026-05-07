#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_policy_info
version_added: "1.9.0"
short_description: Gather information about AWS IAM inline policies
description:
  - Gathers information about AWS IAM inline policies for users and groups.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about IAM inline policies
  linuxhq.aws.iam_policy_info:
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
        policy_names = paginated_query_with_retries(
            client,
            list_operation,
            **scrub_none_parameters(
                snake_dict_to_camel_dict(
                    {f"{entity_type.lower()}_name": name},
                    capitalize_first=True,
                )
            ),
        ).get("PolicyNames", [])
        results.append(
            {
                "name": name,
                "all_policy_names": policy_names,
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


def main():
    module = AnsibleAWSModule(
        argument_spec={},
        supports_check_mode=True,
    )
    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())
    groups = paginated_query_with_retries(client, "list_groups").get("Groups", [])
    users = paginated_query_with_retries(client, "list_users").get("Users", [])
    group_names = [group["GroupName"] for group in groups if group.get("GroupName")]
    user_names = [user["UserName"] for user in users if user.get("UserName")]

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
