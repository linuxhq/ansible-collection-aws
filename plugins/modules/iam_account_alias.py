#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_account_alias
short_description: Manage aws iam account alias
description:
  - Manages the AWS IAM account alias for the current account.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The IAM account alias name.
    required: true
    type: str
  state:
    description:
      - Whether the IAM account alias should exist.
    choices:
      - absent
      - present
    default: present
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Ensure an IAM account alias is present
  linuxhq.aws.iam_account_alias:
    name: molecule-2026-05-03

- name: Ensure an IAM account alias is absent
  linuxhq.aws.iam_account_alias:
    name: molecule-2026-05-03
    state: absent
"""

RETURN = r"""
account_aliases:
  description:
    - The IAM account aliases after module execution.
  returned: always
  type: list
  elements: str
name:
  description:
    - The requested IAM account alias.
  returned: always
  type: str
state:
  description:
    - The requested state of the IAM account alias.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry


def list_account_aliases(client, module):
    try:
        return sorted(
            paginated_query_with_retries(client, "list_account_aliases").get(
                "AccountAliases", []
            )
        )
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to list AWS IAM account aliases")


def ensure_absent(client, module):
    name = module.params["name"]
    aliases = list_account_aliases(client, module)
    desired_aliases = []
    for alias in aliases:
        if alias != name:
            desired_aliases.append(alias)

    changed = name in aliases

    if changed and not module.check_mode:
        try:
            client.delete_account_alias(
                AccountAlias=name,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to delete AWS IAM account alias {name}"
            )

        aliases = desired_aliases
    elif changed and module.check_mode:
        aliases = desired_aliases

    module.exit_json(
        changed=changed,
        account_aliases=aliases,
        name=name,
        state="absent",
    )


def ensure_present(client, module):
    name = module.params["name"]
    aliases = list_account_aliases(client, module)
    desired_aliases = [name]
    changed = aliases != desired_aliases

    if changed and not module.check_mode:
        for alias in aliases:
            if alias in desired_aliases:
                continue

            try:
                client.delete_account_alias(
                    AccountAlias=alias,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to delete AWS IAM account alias {alias}"
                )

        for alias in desired_aliases:
            if alias in aliases:
                continue

            try:
                client.create_account_alias(
                    AccountAlias=alias,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to create AWS IAM account alias {alias}"
                )

        aliases = desired_aliases
    elif changed and module.check_mode:
        aliases = desired_aliases

    module.exit_json(
        changed=changed,
        account_aliases=aliases,
        name=name,
        state="present",
    )


def main():
    module = AnsibleAWSModule(
        argument_spec={
            "name": {"required": True, "type": "str"},
            "state": {
                "choices": ["absent", "present"],
                "default": "present",
                "type": "str",
            },
        },
        supports_check_mode=True,
    )
    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    method_names = {"list_account_aliases"}
    if state == "present":
        method_names.update({"create_account_alias", "delete_account_alias"})
    elif state == "absent":
        method_names.add("delete_account_alias")
    else:
        module.fail_json(msg=f"Unsupported state: {state}")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support IAM {method_name}"
            )

    required_method_parameters = {
        "create_account_alias": {"AccountAlias"},
        "delete_account_alias": {"AccountAlias"},
    }
    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in parameter_names:
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support IAM "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
