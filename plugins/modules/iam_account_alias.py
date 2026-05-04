#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: iam_account_alias
version_added: 1.9.1
short_description: Manage AWS IAM account aliases
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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def list_account_aliases(client, module):
    aliases = []
    marker = None

    while True:
        kwargs = {}
        if marker:
            kwargs["Marker"] = marker

        try:
            response = client.list_account_aliases(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS IAM account aliases",
            )

        aliases.extend(response.get("AccountAliases", []))
        if not response.get("IsTruncated"):
            break
        marker = response.get("Marker")

    return aliases


def ensure_present(client, module):
    name = module.params["name"]
    aliases = list_account_aliases(client, module)
    changed = aliases != [name]

    if changed and not module.check_mode:
        for alias in aliases:
            if alias == name:
                continue
            try:
                client.delete_account_alias(AccountAlias=alias)
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to delete AWS IAM account alias {alias}",
                )

        if name not in aliases:
            try:
                client.create_account_alias(AccountAlias=name)
            except Exception as e:
                module.fail_json_aws(
                    e,
                    msg=f"Unable to create AWS IAM account alias {name}",
                )

        aliases = list_account_aliases(client, module)
    elif changed and module.check_mode:
        aliases = [name]

    module.exit_json(
        changed=changed,
        account_aliases=aliases,
        name=name,
        state="present",
    )


def ensure_absent(client, module):
    name = module.params["name"]
    aliases = list_account_aliases(client, module)
    changed = name in aliases

    if changed and not module.check_mode:
        try:
            client.delete_account_alias(AccountAlias=name)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to delete AWS IAM account alias {name}",
            )
        aliases = list_account_aliases(client, module)
    elif changed and module.check_mode:
        aliases = [alias for alias in aliases if alias != name]

    module.exit_json(
        changed=changed,
        account_aliases=aliases,
        name=name,
        state="absent",
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
    client = module.client("iam")

    if module.params["state"] == "present":
        ensure_present(client, module)

    ensure_absent(client, module)


if __name__ == "__main__":
    main()
