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

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry


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
    groups = list_iam_entities(client, module, "list_groups", "Groups")
    return build_entity_policies(
        client,
        module,
        "Group",
        [group["GroupName"] for group in groups],
    )


def get_inline_policy(client, module, operation, entity_type, entity_name, policy_name):
    get_policy = AWSRetry.jittered_backoff()(getattr(client, operation))
    try:
        response = get_policy(
            **{
                f"{entity_type}Name": entity_name,
                "PolicyName": policy_name,
            }
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS IAM {entity_type.lower()} inline policy {policy_name} for {entity_name}",
        )

    return {
        "policy_name": response.get("PolicyName", policy_name),
        "policy_document": response.get("PolicyDocument"),
    }


def get_user_inline_policies(client, module):
    users = list_iam_entities(client, module, "list_users", "Users")
    return build_entity_policies(
        client,
        module,
        "User",
        [user["UserName"] for user in users],
    )


def list_iam_entities(client, module, operation, result_key):
    try:
        response = paginated_query_with_retries(client, operation)
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list AWS IAM {result_key.lower()}",
        )
    return response.get(result_key, [])


def list_inline_policy_names(client, module, operation, entity_type, entity_name):
    try:
        response = paginated_query_with_retries(
            client,
            operation,
            **{f"{entity_type}Name": entity_name},
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to list AWS IAM {entity_type.lower()} inline policies for {entity_name}",
        )
    return response.get("PolicyNames", [])


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
