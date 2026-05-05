#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_policy_info
version_added: 1.9.1
short_description: Gather information about AWS IAM inline policies
description:
  - Gathers information about AWS IAM inline policies for users and groups.
author:
  - Taylor Kimball (@tkimball83)
extends_documentation_fragment:
  - amazon.aws.common.modules
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_response,
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
        policy_names = list_inline_policy_names(
            client, module, list_operation, entity_type, name
        )
        results.append(
            {
                "name": name,
                "all_policy_names": policy_names,
                "policies": [
                    get_inline_policy(
                        client,
                        module,
                        get_operation,
                        entity_type,
                        name,
                        policy_name,
                    )
                    for policy_name in policy_names
                ],
                "policy_names": policy_names,
            }
        )

    return results


def get_group_inline_policies(client, module):
    groups = aws_paginated_list(client, module, "list_groups", "Groups")
    return build_entity_policies(
        client,
        module,
        "Group",
        [group["GroupName"] for group in groups],
    )


def get_inline_policy(client, module, operation, entity_type, entity_name, policy_name):
    response = aws_response(
        client,
        module,
        operation,
        **{
            f"{entity_type}Name": entity_name,
            "PolicyName": policy_name,
        },
    )

    return {
        "policy_name": response.get("PolicyName", policy_name),
        "policy_document": response.get("PolicyDocument"),
    }


def get_user_inline_policies(client, module):
    users = aws_paginated_list(client, module, "list_users", "Users")

    return build_entity_policies(
        client,
        module,
        "User",
        [user["UserName"] for user in users],
    )


def list_inline_policy_names(client, module, operation, entity_type, entity_name):
    return aws_paginated_list(
        client,
        module,
        operation,
        "PolicyNames",
        **{f"{entity_type}Name": entity_name},
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={},
        supports_check_mode=True,
    )
    client = module.client("iam")

    module.exit_json(
        changed=False,
        group_policies=get_group_inline_policies(client, module),
        user_policies=get_user_inline_policies(client, module),
    )


if __name__ == "__main__":
    main()
