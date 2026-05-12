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

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)


def ensure_absent(client, module):
    name = module.params["name"]
    aliases = sorted(
        paginated_query_with_retries(client, "list_account_aliases").get(
            "AccountAliases", []
        )
    )
    desired_aliases = [alias for alias in aliases if alias != name]
    changed = name in aliases

    if changed and not module.check_mode:
        try:
            client.delete_account_alias(
                **scrub_none_parameters(
                    snake_dict_to_camel_dict(
                        {"account_alias": name}, capitalize_first=True
                    )
                ),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to delete AWS IAM account alias {name}"
            )
        aliases = paginated_query_with_retries(client, "list_account_aliases").get(
            "AccountAliases", []
        )
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
    aliases = sorted(
        paginated_query_with_retries(client, "list_account_aliases").get(
            "AccountAliases", []
        )
    )
    desired_aliases = [name]
    changed = aliases != desired_aliases

    if changed and not module.check_mode:
        for alias in [alias for alias in aliases if alias not in desired_aliases]:
            try:
                client.delete_account_alias(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {"account_alias": alias}, capitalize_first=True
                        )
                    ),
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to delete AWS IAM account alias {alias}"
                )

        for alias in [alias for alias in desired_aliases if alias not in aliases]:
            try:
                client.create_account_alias(
                    **scrub_none_parameters(
                        snake_dict_to_camel_dict(
                            {"account_alias": alias}, capitalize_first=True
                        )
                    ),
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to create AWS IAM account alias {alias}"
                )

        aliases = paginated_query_with_retries(client, "list_account_aliases").get(
            "AccountAliases", []
        )
    elif changed and module.check_mode:
        aliases = [name]

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

    if module.params["state"] == "present":
        ensure_present(client, module)

    ensure_absent(client, module)


if __name__ == "__main__":
    main()
