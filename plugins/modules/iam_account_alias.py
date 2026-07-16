#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - When O(state=present), this must be 3 to 63 characters of lowercase
        letters, digits, and hyphens, and cannot start or end with a hyphen
        or contain consecutive hyphens.
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

import re

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    require_client_methods,
)


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

    if changed:
        if not module.check_mode:
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

    if changed:
        if not module.check_mode:
            try:
                client.create_account_alias(
                    AccountAlias=name,
                    aws_retry=True,
                )
            except Exception as e:
                module.fail_json_aws(
                    e, msg=f"Unable to create AWS IAM account alias {name}"
                )

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

    state = module.params["state"]

    if state == "present" and not re.fullmatch(
        r"[a-z0-9]([a-z0-9]|-(?!-)){1,61}[a-z0-9]", module.params["name"]
    ):
        module.fail_json(
            msg=(
                "name must be 3 to 63 characters of lowercase letters, digits, "
                "and hyphens, and cannot start or end with a hyphen or contain "
                "consecutive hyphens"
            )
        )

    client = module.client("iam", retry_decorator=AWSRetry.jittered_backoff())
    methods = {"list_account_aliases": ()}
    if state == "present":
        methods["create_account_alias"] = ("AccountAlias",)
    if state == "absent":
        methods["delete_account_alias"] = ("AccountAlias",)

    require_client_methods(module, client, "IAM", methods)

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
