#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_policy_info
short_description: Gather information about AWS IAM inline policies
version_added: "1.9.0"
description:
  - Gathers information about AWS IAM inline policies for users and groups.
author:
  - Taylor Kimball (@tkimball83)
options:
  group_name:
    description:
      - IAM group name used to limit group inline policy results.
      - When omitted, all groups matching O(path_prefix) are queried.
      - A group that does not exist is not included in the results.
    type: str
  path_prefix:
    description:
      - IAM path prefix used when listing users and groups.
      - Not used for users when O(user_name) is provided, or for groups
        when O(group_name) is provided.
      - Must begin and end with C(/) and contain at most 512 characters.
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
      - A user that does not exist is not included in the results.
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module does not modify state.
    support: full
  diff_mode:
    description: This module does not modify state.
    support: none
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

- name: Gather information about one inline policy for a selected group
  linuxhq.aws.iam_policy_info:
    group_name: molecule
    policy_name: molecule-s3
"""

RETURN = r"""
group_policies:
  description:
    - The IAM group inline policy information.
    - Each entry contains C(name), C(all_policy_names), C(policy_names),
      and C(policies).
    - C(policies[].policy_document) is returned as provided by the IAM API.
  returned: always
  type: list
  elements: dict
  contains:
    all_policy_names:
      description: All inline policy names attached to the group.
      returned: always
      type: list
      elements: str
    name:
      description: The IAM group name.
      returned: always
      type: str
    policies:
      description: The selected inline policy documents.
      returned: always
      type: list
      elements: dict
      contains:
        policy_document:
          description: The IAM policy document.
          returned: always
          type: dict
        policy_name:
          description: The inline policy name.
          returned: always
          type: str
    policy_names:
      description: Inline policy names selected by O(policy_name).
      returned: always
      type: list
      elements: str
user_policies:
  description:
    - The IAM user inline policy information.
    - Each entry contains C(name), C(all_policy_names), C(policy_names),
      and C(policies).
    - C(policies[].policy_document) is returned as provided by the IAM API.
  returned: always
  type: list
  elements: dict
  contains:
    all_policy_names:
      description: All inline policy names attached to the user.
      returned: always
      type: list
      elements: str
    name:
      description: The IAM user name.
      returned: always
      type: str
    policies:
      description: The selected inline policy documents.
      returned: always
      type: list
      elements: dict
      contains:
        policy_document:
          description: The IAM policy document.
          returned: always
          type: dict
        policy_name:
          description: The inline policy name.
          returned: always
          type: str
    policy_names:
      description: Inline policy names selected by O(policy_name).
      returned: always
      type: list
      elements: str
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)


def validate_policy_names(module, response, entity_type, name):
    valid = (
        isinstance(response, dict)
        and isinstance(response.get("PolicyNames"), list)
        and all(isinstance(policy_name, str) for policy_name in response["PolicyNames"])
    )
    if not valid:
        module.fail_json(
            msg=(f"Unable to list AWS IAM {entity_type.lower()} policies for {name}: AWS returned an invalid response")
        )

    return response["PolicyNames"]


def validate_policy_document(module, response, entity_type, name, policy_name):
    if not isinstance(response, dict) or not isinstance(response.get("PolicyDocument"), dict):
        module.fail_json(
            msg=(
                f"Unable to get AWS IAM {entity_type.lower()} policy {policy_name} "
                f"for {name}: AWS returned an invalid response"
            )
        )

    return response["PolicyDocument"]


def build_entity_policies(client, module, entity_type, names):
    desired_policy_name = module.params["policy_name"]
    if entity_type == "Group":
        list_operation = "list_group_policies"
        get_operation = "get_group_policy"
    else:
        list_operation = "list_user_policies"
        get_operation = "get_user_policy"

    results = []
    if names:
        require_client_methods(
            module,
            client,
            "IAM",
            {list_operation: (f"{entity_type}Name", "Marker", "MaxItems")},
        )

    get_policy = None

    for name in names:
        try:
            response = paginated_query_with_retries(
                client,
                list_operation,
                **{f"{entity_type}Name": name},
            )
        except is_boto3_error_code("NoSuchEntity"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list AWS IAM {entity_type.lower()} policies for {name}",
            )

        all_policy_names = validate_policy_names(module, response, entity_type, name)

        policy_names = all_policy_names
        if desired_policy_name:
            policy_names = [policy_name for policy_name in all_policy_names if policy_name == desired_policy_name]

        policies = []
        if policy_names and get_policy is None:
            require_client_methods(
                module,
                client,
                "IAM",
                {get_operation: (f"{entity_type}Name", "PolicyName")},
            )
            get_policy = getattr(client, get_operation)

        for policy_name in policy_names:
            try:
                response = get_policy(
                    **{f"{entity_type}Name": name, "PolicyName": policy_name},
                    aws_retry=True,
                )
            except is_boto3_error_code("NoSuchEntity"):
                continue
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e,
                    msg=(f"Unable to get AWS IAM {entity_type.lower()} policy " f"{policy_name} for {name}"),
                )

            policy_document = validate_policy_document(module, response, entity_type, name, policy_name)

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
    path_prefix = module.params["path_prefix"]
    request = {}
    if path_prefix:
        request["PathPrefix"] = path_prefix

    require_client_methods(
        module,
        client,
        "IAM",
        {f"list_{entity_type.lower()}s": tuple(request) + ("Marker", "MaxItems")},
    )

    entities = query_list(
        module,
        client,
        f"list_{entity_type.lower()}s",
        response_key,
        f"Unable to list AWS IAM {entity_type.lower()}s",
        **request,
    )

    valid = isinstance(entities, list) and all(
        isinstance(entity, dict) and isinstance(entity.get(name_key), str) and entity[name_key] for entity in entities
    )
    if not valid:
        module.fail_json(msg=f"Unable to list AWS IAM {entity_type.lower()}s: AWS returned an invalid response")

    return [entity[name_key] for entity in entities]


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
    path_prefix = module.params["path_prefix"]
    if path_prefix and (not path_prefix.startswith("/") or not path_prefix.endswith("/") or len(path_prefix) > 512):
        module.fail_json(msg="path_prefix must begin and end with / and contain at most 512 characters")

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
