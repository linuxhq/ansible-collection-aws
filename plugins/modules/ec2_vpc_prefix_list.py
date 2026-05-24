#!/usr/bin/python

# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_prefix_list
short_description: Manage aws virtual private cloud prefix lists
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
  purge_tags:
    description:
      - Whether tags not listed in O(tags) should be removed.
      - This option is only used when O(tags) is provided.
    default: true
    type: bool
  state:
    description:
      - Whether the managed prefix list should exist.
    choices:
      - absent
      - present
    default: present
    type: str
  tags:
    description:
      - Tags to apply to the managed prefix list.
    type: dict
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
    tags:
      Name: linuxhq-localhost

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

import json

from ansible.module_utils.common.dict_transformations import (
    recursive_diff,
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
    boto3_tag_specifications,
    compare_aws_tags,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
    scrub_none_parameters,
)
from ansible_collections.amazon.aws.plugins.module_utils.waiter import (
    BaseWaiterFactory,
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
    "managed_prefix_list_deleted": {
        "delay": 1,
        "maxAttempts": 60,
        "operation": "DescribeManagedPrefixLists",
        "acceptors": [
            {
                "expected": "InvalidPrefixListID.NotFound",
                "matcher": "error",
                "state": "success",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "delete-in-progress",
                "matcher": "path",
                "state": "retry",
            },
        ],
    },
}


class EC2WaiterFactory(BaseWaiterFactory):
    @property
    def _waiter_model_data(self):
        return EC2_WAITER_MODEL_DATA


def create_prefix_list(client, module, desired_prefix_list, desired_entries):
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            dict(desired_prefix_list, entries=desired_entries),
            capitalize_first=True,
        )
    )
    if module.params["tags"] is not None:
        tag_specifications = boto3_tag_specifications(
            module.params["tags"], types="prefix-list"
        )
        if tag_specifications is not None:
            request["TagSpecifications"] = tag_specifications

    try:
        prefix_list = client.create_managed_prefix_list(
            **request,
            aws_retry=True,
        ).get("PrefixList", {})
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to create EC2 VPC managed prefix list "
                f"{module.params['name']}"
            ),
        )
    created_prefix_list_id = prefix_list.get("PrefixListId")
    if created_prefix_list_id:
        wait_for_ready_state(client, module, created_prefix_list_id)
    return get_current(client, module)


def delete_prefix_list(client, module, prefix_list_id):
    try:
        client.delete_managed_prefix_list(
            PrefixListId=prefix_list_id,
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to delete EC2 VPC managed prefix list "
                f"{module.params['name']}"
            ),
        )
    if prefix_list_id:
        wait_for_prefix_list_state(
            client,
            module,
            prefix_list_id,
            "managed_prefix_list_deleted",
        )


def ensure_absent(client, module):
    current = get_customer_managed_prefix_list_by_name(client, module.params["name"])
    changed = current is not None
    prefix_list_id = (current or {}).get("PrefixListId")

    if changed and not module.check_mode:
        delete_prefix_list(client, module, prefix_list_id)

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "absent",
    }
    if prefix_list_id:
        result["prefix_list_id"] = prefix_list_id
    module.exit_json(**result)


def ensure_present(client, module):
    current, current_entries = get_current(client, module)
    desired_entries = comparable_entries(module.params["entries"])
    if not desired_entries:
        module.fail_json(
            msg="entries must contain at least one item when state=present"
        )

    changed = current is None

    desired_prefix_list = {
        "address_family": module.params["address_family"],
        "max_entries": len(desired_entries),
        "prefix_list_name": module.params["name"],
    }

    if current is None:
        if not module.check_mode:
            current, current_entries = create_prefix_list(
                client,
                module,
                desired_prefix_list,
                desired_entries,
            )
        else:
            current = snake_dict_to_camel_dict(
                desired_prefix_list, capitalize_first=True
            )
            if module.params["tags"] is not None:
                current["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
            current_entries = desired_entries
    else:
        current_prefix_list = comparable_prefix_list(current)
        current_entries = comparable_entries(current_entries)
        remove_entries = [
            entry for entry in current_entries if entry not in desired_entries
        ]
        add_entries = [
            entry for entry in desired_entries if entry not in current_entries
        ]
        resource_changed = (
            recursive_diff((current_prefix_list) or {}, (desired_prefix_list) or {})
            is not None
        )
        changed = bool(remove_entries or add_entries or resource_changed)
        tags_to_set, tag_keys_to_unset = ({}, [])
        if module.params["tags"] is not None:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
                module.params["tags"],
                purge_tags=module.params["purge_tags"],
            )
        changed = bool(changed or tags_to_set or tag_keys_to_unset)

        if changed and not module.check_mode:
            if remove_entries:
                modify_prefix_list(
                    client,
                    module,
                    current,
                    remove_entries=[
                        {"cidr": entry["cidr"]} for entry in remove_entries
                    ],
                )
                wait_for_ready_state(
                    client,
                    module,
                    current.get("PrefixListId"),
                )
                current, current_entries = get_current(client, module)

            if resource_changed:
                current_prefix_list = comparable_prefix_list(current)
                if (
                    recursive_diff(
                        (current_prefix_list) or {}, (desired_prefix_list) or {}
                    )
                    is not None
                ):
                    modify_prefix_list(
                        client,
                        module,
                        current,
                        max_entries=len(desired_entries),
                    )
                    wait_for_ready_state(
                        client,
                        module,
                        current.get("PrefixListId"),
                    )
                    current, current_entries = get_current(client, module)
                    current_prefix_list = comparable_prefix_list(current)

                if (
                    recursive_diff(
                        (current_prefix_list) or {}, (desired_prefix_list) or {}
                    )
                    is not None
                ):
                    prefix_list_id = current.get("PrefixListId")
                    delete_prefix_list(client, module, prefix_list_id)
                    current, current_entries = create_prefix_list(
                        client,
                        module,
                        desired_prefix_list,
                        desired_entries,
                    )
                    add_entries = []

            if add_entries:
                modify_prefix_list(
                    client,
                    module,
                    current,
                    add_entries=add_entries,
                )
                wait_for_ready_state(
                    client,
                    module,
                    current.get("PrefixListId"),
                )
                current, current_entries = get_current(client, module)
            if current is not None and module.params["tags"] is not None:
                tags_to_set, tag_keys_to_unset = compare_aws_tags(
                    boto3_tag_list_to_ansible_dict((current or {}).get("Tags", [])),
                    module.params["tags"],
                    purge_tags=module.params["purge_tags"],
                )
                apply_tag_changes(
                    client,
                    module,
                    current.get("PrefixListId"),
                    tags_to_set,
                    tag_keys_to_unset,
                )
                current = prefix_list_with_updated_tags(
                    current, tags_to_set, tag_keys_to_unset
                )
        elif changed and module.check_mode:
            current = dict(current)
            current.update(
                snake_dict_to_camel_dict(desired_prefix_list, capitalize_first=True)
            )
            if module.params["tags"] is not None:
                current["Tags"] = ansible_dict_to_boto3_tag_list(module.params["tags"])
            current_entries = desired_entries

    result = {
        "changed": changed,
        "name": module.params["name"],
        "prefix_list": normalize_prefix_list(current, current_entries),
        "state": "present",
    }
    prefix_list_id = (current or {}).get("PrefixListId")
    if prefix_list_id:
        result["prefix_list_id"] = prefix_list_id
    module.exit_json(**result)


def get_current(client, module):
    prefix_list = get_customer_managed_prefix_list_by_name(
        client, module.params["name"]
    )
    if prefix_list is None:
        return None, None

    entries = get_managed_prefix_list_entries(client, prefix_list.get("PrefixListId"))
    return prefix_list, entries


def modify_prefix_list(client, module, current, **kwargs):
    request = {
        "prefix_list_id": current.get("PrefixListId"),
    }
    if "add_entries" in kwargs or "remove_entries" in kwargs:
        request["current_version"] = current.get("Version")
    request.update(kwargs)

    try:
        client.modify_managed_prefix_list(
            **scrub_none_parameters(
                snake_dict_to_camel_dict(request, capitalize_first=True)
            ),
            aws_retry=True,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to modify EC2 VPC managed prefix list "
                f"{module.params['name']}"
            ),
        )


def wait_for_ready_state(client, module, prefix_list_id):
    wait_for_prefix_list_state(
        client,
        module,
        prefix_list_id,
        "managed_prefix_list_ready",
    )


def wait_for_prefix_list_state(client, module, prefix_list_id, waiter_name):
    try:
        waiter = EC2WaiterFactory().get_waiter(client, waiter_name)
        waiter.wait(PrefixListIds=[prefix_list_id])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Timed out waiting for EC2 VPC managed prefix list {prefix_list_id}",
        )


def get_customer_managed_prefix_list_by_name(client, name):
    filters = ansible_dict_to_boto3_filter_list({"prefix-list-name": name})
    prefix_lists = paginated_query_with_retries(
        client, "describe_managed_prefix_lists", Filters=filters
    ).get("PrefixLists", [])
    return next(
        (
            prefix_list
            for prefix_list in prefix_lists
            if prefix_list.get("PrefixListName") == name
            and prefix_list.get("OwnerId") != "AWS"
        ),
        None,
    )


def get_managed_prefix_list_entries(client, prefix_list_id):
    return paginated_query_with_retries(
        client,
        "get_managed_prefix_list_entries",
        PrefixListId=prefix_list_id,
    ).get("Entries", [])


def apply_tag_changes(client, module, prefix_list_id, tags_to_set, tag_keys_to_unset):
    if not prefix_list_id:
        return
    if tag_keys_to_unset:
        try:
            client.delete_tags(
                Resources=[prefix_list_id],
                Tags=[{"Key": key} for key in tag_keys_to_unset],
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to remove tags from EC2 VPC managed prefix list {prefix_list_id}",
            )
    if tags_to_set:
        try:
            client.create_tags(
                Resources=[prefix_list_id],
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to tag EC2 VPC managed prefix list {prefix_list_id}",
            )


def prefix_list_with_updated_tags(prefix_list, tags_to_set, tag_keys_to_unset):
    prefix_list = dict(prefix_list)
    tags = boto3_tag_list_to_ansible_dict((prefix_list or {}).get("Tags", []))
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)
    tags.update(tags_to_set)
    prefix_list["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return prefix_list


def comparable_prefix_list(prefix_list):
    normalized = boto3_resource_to_ansible_dict(
        prefix_list, transform_tags=False, force_tags=False
    )
    return {
        "address_family": normalized.get("address_family"),
        "max_entries": normalized.get("max_entries"),
        "prefix_list_name": normalized.get("prefix_list_name"),
    }


def comparable_entries(entries):
    normalized_entries = boto3_resource_list_to_ansible_dict(
        entries, transform_tags=False, force_tags=False
    )
    result = []
    for entry in normalized_entries or []:
        result.append(
            {
                field: entry.get(field)
                for field in ("cidr", "description")
                if entry.get(field) is not None
            }
        )
    return sorted(result, key=lambda entry: json.dumps(entry, sort_keys=True))


def normalize_prefix_list(prefix_list, entries=None):
    normalized = boto3_resource_to_ansible_dict(
        prefix_list or {}, transform_tags=True, force_tags=False
    )
    if entries is not None:
        normalized["entries"] = boto3_resource_list_to_ansible_dict(
            entries, transform_tags=False, force_tags=False
        )
    return normalized


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
        "purge_tags": {"default": True, "type": "bool"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"type": "dict"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["entries"])],
        supports_check_mode=True,
    )
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    state = module.params["state"]
    if state == "present":
        ensure_present(client, module)
    elif state == "absent":
        ensure_absent(client, module)
    else:
        module.fail_json(msg=f"Unsupported state: {state}")


if __name__ == "__main__":
    main()
