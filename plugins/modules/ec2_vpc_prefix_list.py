#!/usr/bin/python

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_prefix_list
version_added: 1.9.1
short_description: Manage EC2 VPC managed prefix lists
description:
  - Creates, updates, and deletes EC2 VPC managed prefix lists.
  - Manages prefix list entries idempotently.
author:
  - Taylor Kimball (@tkimball83)
options:
  address_family:
    description:
      - The address family for the managed prefix list.
    choices:
      - IPv4
      - IPv6
    default: IPv4
    type: str
  entries:
    description:
      - The prefix list entries to manage.
      - Each entry must include O(entries[].cidr) and may include O(entries[].description).
    elements: dict
    suboptions:
      cidr:
        description:
          - The CIDR block for the prefix list entry.
        required: true
        type: str
      description:
        description:
          - The description for the prefix list entry.
        type: str
    type: list
  name:
    description:
      - The managed prefix list name.
    required: true
    type: str
  state:
    description:
      - Whether the managed prefix list should exist.
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
- name: Ensure a managed prefix list is present
  linuxhq.aws.ec2_vpc_prefix_list:
    name: linuxhq-localhost
    entries:
      - cidr: 127.0.0.1/32
        description: localhost-1
      - cidr: 127.0.0.2/32
        description: localhost-2

- name: Ensure a managed prefix list is absent
  linuxhq.aws.ec2_vpc_prefix_list:
    name: linuxhq-localhost
    state: absent
"""

RETURN = r"""
name:
  description: The managed prefix list name.
  returned: always
  type: str
prefix_list:
  description:
    - The current managed prefix list after module execution.
  returned: when state is present
  type: dict
prefix_list_id:
  description: The managed prefix list identifier.
  returned: when a prefix list exists
  type: str
state:
  description: The requested state of the managed prefix list.
  returned: always
  type: str
"""

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_list,
    aws_response,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.comparison import (
    aws_resource_list_to_snake_dicts,
    aws_resource_to_snake_dict,
    canonicalize_list,
    list_difference,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    wait_for_aws_resource,
)

EC2_WAITER_MODEL_DATA = {
    "managed_prefix_list_ready": {
        "delay": 1,
        "maxAttempts": 60,
        "operation": "DescribeManagedPrefixLists",
        "acceptors": [
            {
                "argument": "PrefixLists[0].State",
                "expected": "create-complete",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "modify-complete",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "create-in-progress",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "modify-in-progress",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "restore-in-progress",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}


def aws_add_entry(entry):
    aws_entry = {"Cidr": entry["cidr"]}
    if entry.get("description") is not None:
        aws_entry["Description"] = entry["description"]
    return aws_entry


def aws_add_entries(entries):
    return [aws_add_entry(entry) for entry in entries]


def aws_remove_entries(entries):
    return [{"Cidr": entry["cidr"]} for entry in entries]


def canonical_entry(entry):
    normalized = {"cidr": entry["cidr"]}
    if entry.get("description") is not None:
        normalized["description"] = entry["description"]
    return normalized


def canonicalize_entries(entries):
    return canonicalize_list(entries, canonical_entry)


def diff_entries(left, right):
    return list_difference(left, right, canonical_entry)


def get_prefix_list_entries(client, module, prefix_list_id):
    return aws_resource_list_to_snake_dicts(
        aws_paginated_list(
            client,
            module,
            "get_managed_prefix_list_entries",
            "Entries",
            PrefixListId=prefix_list_id,
        )
    )


def normalize_prefix_list(prefix_list, entries=None):
    normalized = aws_resource_to_snake_dict(prefix_list or {})
    if entries is not None:
        normalized["entries"] = entries
    return normalized


def find_prefix_list(client, module, name):
    for prefix_list in aws_paginated_list(
        client,
        module,
        "describe_managed_prefix_lists",
        "PrefixLists",
    ):
        if (
            prefix_list.get("PrefixListName") == name
            and prefix_list.get("OwnerId") != "AWS"
        ):
            entries = get_prefix_list_entries(
                client, module, prefix_list["PrefixListId"]
            )
            return prefix_list, entries
    return None, None


def wait_for_ready_state(client, module, prefix_list_id):
    wait_for_aws_resource(
        client,
        module,
        EC2_WAITER_MODEL_DATA,
        "managed_prefix_list_ready",
        f"Timed out waiting for EC2 VPC managed prefix list {prefix_list_id}",
        waiter_config={"Delay": 1, "MaxAttempts": 60},
        PrefixListIds=[prefix_list_id],
    )


def get_current(client, module):
    prefix_list, entries = find_prefix_list(client, module, module.params["name"])
    if prefix_list is None:
        return None, None
    return prefix_list, entries


def modify_prefix_list(client, module, current, **kwargs):
    request = {
        "PrefixListId": current["PrefixListId"],
    }
    if "AddEntries" in kwargs or "RemoveEntries" in kwargs:
        request["CurrentVersion"] = current["Version"]
    request.update(kwargs)

    aws_response(
        client,
        module,
        "modify_managed_prefix_list",
        error_message=(
            "Unable to modify EC2 VPC managed prefix list " f"{module.params['name']}"
        ),
        **request,
    )


def ensure_present(client, module):
    desired_entries = canonicalize_entries(module.params["entries"])
    if not desired_entries:
        module.fail_json(
            msg="entries must contain at least one item when state=present"
        )

    current, current_entries = get_current(client, module)
    changed = current is None

    if (
        current is not None
        and current.get("AddressFamily") != module.params["address_family"]
    ):
        module.fail_json(
            msg=(
                f"EC2 VPC managed prefix list {module.params['name']} already exists with "
                f"address_family {current.get('AddressFamily')}"
            )
        )

    if current is None:
        if not module.check_mode:
            response = aws_response(
                client,
                module,
                "create_managed_prefix_list",
                error_message=(
                    "Unable to create EC2 VPC managed prefix list "
                    f"{module.params['name']}"
                ),
                AddressFamily=module.params["address_family"],
                Entries=aws_add_entries(desired_entries),
                MaxEntries=len(desired_entries),
                PrefixListName=module.params["name"],
            )
            prefix_list = response.get("PrefixList", {})
            if prefix_list.get("PrefixListId"):
                wait_for_ready_state(client, module, prefix_list["PrefixListId"])
            current, current_entries = get_current(client, module)
        else:
            current = {
                "AddressFamily": module.params["address_family"],
                "MaxEntries": len(desired_entries),
                "PrefixListName": module.params["name"],
            }
            current_entries = desired_entries
    else:
        remove_entries = diff_entries(current_entries, desired_entries)
        add_entries = diff_entries(desired_entries, current_entries)
        max_entries_changed = len(desired_entries) != current.get("MaxEntries")
        changed = bool(remove_entries or add_entries or max_entries_changed)

        if changed and not module.check_mode:
            if remove_entries:
                modify_prefix_list(
                    client,
                    module,
                    current,
                    RemoveEntries=aws_remove_entries(remove_entries),
                )
                wait_for_ready_state(client, module, current["PrefixListId"])
                current, current_entries = get_current(client, module)

            if len(desired_entries) != current.get("MaxEntries"):
                modify_prefix_list(
                    client, module, current, MaxEntries=len(desired_entries)
                )
                wait_for_ready_state(client, module, current["PrefixListId"])
                current, current_entries = get_current(client, module)

            if add_entries:
                modify_prefix_list(
                    client,
                    module,
                    current,
                    AddEntries=aws_add_entries(add_entries),
                )
                wait_for_ready_state(client, module, current["PrefixListId"])
                current, current_entries = get_current(client, module)
        elif changed and module.check_mode:
            current = dict(current)
            current["MaxEntries"] = len(desired_entries)
            current_entries = desired_entries

    result = {
        "changed": changed,
        "name": module.params["name"],
        "prefix_list": normalize_prefix_list(current, current_entries),
        "state": "present",
    }
    if current and current.get("PrefixListId"):
        result["prefix_list_id"] = current["PrefixListId"]
    module.exit_json(**result)


def ensure_absent(client, module):
    current, _ = get_current(client, module)
    changed = current is not None

    if changed and not module.check_mode:
        aws_response(
            client,
            module,
            "delete_managed_prefix_list",
            error_message=(
                "Unable to delete EC2 VPC managed prefix list "
                f"{module.params['name']}"
            ),
            PrefixListId=current["PrefixListId"],
        )

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "absent",
    }
    if current and current.get("PrefixListId"):
        result["prefix_list_id"] = current["PrefixListId"]
    module.exit_json(**result)


def main():
    argument_spec = {
        "address_family": {
            "choices": ["IPv4", "IPv6"],
            "default": "IPv4",
            "type": "str",
        },
        "entries": {
            "elements": "dict",
            "options": {
                "cidr": {"required": True, "type": "str"},
                "description": {"type": "str"},
            },
            "type": "list",
        },
        "name": {"required": True, "type": "str"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["entries"])],
        supports_check_mode=True,
    )
    client = module.client("ec2")

    if module.params["state"] == "present":
        ensure_present(client, module)
    ensure_absent(client, module)


if __name__ == "__main__":
    main()
