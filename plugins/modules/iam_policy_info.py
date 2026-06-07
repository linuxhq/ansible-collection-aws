#!/usr/bin/python
# -*- coding: utf-8 -*-
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
  group_name:
    description:
      - IAM group name used to limit group inline policy results.
      - When omitted, all groups matching O(path_prefix) are queried.
    type: str
  path_prefix:
    description:
      - IAM path prefix used when listing users and groups.
    type: str
  policy_name:
    description:
      - IAM inline policy name used to limit returned policy documents.
      - The policy name is filtered after listing inline policies for each
        selected user or group.
    type: str
  user_name:
    description:
      - IAM user name used to limit user inline policy results.
      - When omitted, all users matching O(path_prefix) are queried.
    type: str
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
    user_name: molecule

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
        try:
            all_policy_names = paginated_query_with_retries(
                client,
                list_operation,
                **{f"{entity_type}Name": name},
            ).get("PolicyNames", [])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list AWS IAM {entity_type.lower()} policies for {name}",
            )

        policy_names = []
        for policy_name in all_policy_names:
            if (
                module.params["policy_name"]
                and policy_name != module.params["policy_name"]
            ):
                continue

            policy_names.append(policy_name)

        policies = []
        for policy_name in policy_names:
            try:
                policy_document = getattr(client, get_operation)(
                    **{f"{entity_type}Name": name, "PolicyName": policy_name},
                    aws_retry=True,
                ).get("PolicyDocument")
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=(
                        f"Unable to get AWS IAM {entity_type.lower()} policy "
                        f"{policy_name} for {name}"
                    ),
                )

            policies.append(
                {
                    "policy_name": policy_name,
                    "policy_document": policy_document,
                }
            )
        results.append(
            {
                "name": name,
                "all_policy_names": all_policy_names,
                "policies": policies,
                "policy_names": policy_names,
            }
        )

    return results


def entity_names(client, module, entity_type):
    explicit_name = module.params[f"{entity_type.lower()}_name"]

    if explicit_name:
        return [explicit_name]
    response_key = f"{entity_type}s"
    name_key = f"{entity_type}Name"
    request = {}
    if module.params["path_prefix"] is not None:
        request["PathPrefix"] = module.params["path_prefix"]

    try:
        entities = paginated_query_with_retries(
            client,
            f"list_{entity_type.lower()}s",
            **request,
        ).get(response_key, [])
    except Exception as e:
        module.fail_json_aws(e, msg=f"Unable to list AWS IAM {entity_type.lower()}s")

    names = []
    for entity in entities:
        if entity.get(name_key):
            names.append(entity[name_key])

    return names


def main():
    argument_spec = {
        "group_name": {"type": "str"},
        "path_prefix": {"type": "str"},
        "policy_name": {"type": "str"},
        "user_name": {"type": "str"},
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
