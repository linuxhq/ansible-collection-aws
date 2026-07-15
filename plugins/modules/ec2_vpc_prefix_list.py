#!/usr/bin/python
# -*- coding: utf-8 -*-
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
      - Changing this value replaces the managed prefix list.
    choices:
      - IPv4
      - IPv6
    default: IPv4
    type: str
  entries:
    description:
      - The prefix list entries to manage.
      - Each entry must include O(entries[].cidr) and may include O(entries[].description).
      - This is required when O(state=present).
      - This list must contain at least one entry, and entry CIDR blocks must
        be unique.
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
  wait:
    description:
      - Whether to wait for managed prefix list create, update, and delete operations.
    default: true
    type: bool
  wait_delay:
    description:
      - The delay between polling attempts when O(wait=true).
      - This must be 1 or greater.
    default: 1
    type: int
  wait_timeout:
    description:
      - The maximum number of seconds to wait when O(wait=true).
      - This must be 1 or greater.
    default: 60
    type: int
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
  contains:
    entries:
      description:
        - The current managed prefix list entries.
      returned: when entries are available
      type: list
      elements: dict
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
    snake_dict_to_camel_dict,
)
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
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
    custom_waiter_config,
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
    tags = module.params["tags"]
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            dict(desired_prefix_list, entries=desired_entries),
            capitalize_first=True,
        )
    )
    if tags is not None:
        tag_specifications = boto3_tag_specifications(tags, types="prefix-list")

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
            msg=f"Unable to create EC2 VPC managed prefix list {module.params['name']}",
        )

    created_prefix_list_id = prefix_list.get("PrefixListId")

    if created_prefix_list_id and module.params["wait"]:
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
            msg=f"Unable to delete EC2 VPC managed prefix list {module.params['name']}",
        )

    if prefix_list_id and module.params["wait"]:
        wait_for_prefix_list_state(
            client,
            module,
            prefix_list_id,
            "managed_prefix_list_deleted",
        )


def ensure_absent(client, module):
    current = get_customer_managed_prefix_list_by_name(client, module)

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
    name = module.params["name"]
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    wait = module.params["wait"]
    current, current_entries = get_current(client, module)
    desired_entries = comparable_entries(module.params["entries"])

    changed = current is None

    desired_prefix_list = {
        "address_family": module.params["address_family"],
        "max_entries": len(desired_entries),
        "prefix_list_name": name,
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
            if tags is not None:
                current["Tags"] = ansible_dict_to_boto3_tag_list(tags)
            current_entries = desired_entries
    else:
        current_prefix_list = comparable_prefix_list(current)
        current_entries = comparable_entries(current_entries)
        remove_entries = []
        for entry in current_entries:
            if entry not in desired_entries:
                remove_entries.append(entry)

        add_entries = []
        for entry in desired_entries:
            if entry not in current_entries:
                add_entries.append(entry)

        resource_changed = current_prefix_list != desired_prefix_list
        changed = bool(remove_entries or add_entries or resource_changed)
        tags_to_set, tag_keys_to_unset = ({}, [])
        if tags is not None:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )
        changed = bool(changed or tags_to_set or tag_keys_to_unset)

        if changed and not module.check_mode:
            if remove_entries:
                remove_entry_requests = []
                for entry in remove_entries:
                    remove_entry_requests.append({"cidr": entry["cidr"]})

                modify_prefix_list(
                    client,
                    module,
                    current,
                    remove_entries=remove_entry_requests,
                )
                if wait:
                    wait_for_ready_state(
                        client,
                        module,
                        current.get("PrefixListId"),
                    )

                current, current_entries = get_current(client, module)

            if resource_changed:
                current_prefix_list = comparable_prefix_list(current)

                if (current_prefix_list or {}) != desired_prefix_list:
                    modify_prefix_list(
                        client,
                        module,
                        current,
                        max_entries=len(desired_entries),
                    )
                    if wait:
                        wait_for_ready_state(
                            client,
                            module,
                            current.get("PrefixListId"),
                        )

                    current, current_entries = get_current(client, module)
                    current_prefix_list = comparable_prefix_list(current)

                if (current_prefix_list or {}) != desired_prefix_list:
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
                if wait:
                    wait_for_ready_state(
                        client,
                        module,
                        current.get("PrefixListId"),
                    )

                current, current_entries = get_current(client, module)
            if current is not None and tags is not None:
                tags_to_set, tag_keys_to_unset = compare_aws_tags(
                    boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
                    tags,
                    purge_tags=purge_tags,
                )
                prefix_list_id = current.get("PrefixListId")

                if prefix_list_id:
                    if tag_keys_to_unset:
                        tags_to_delete = []
                        for tag_key in tag_keys_to_unset:
                            tags_to_delete.append({"Key": tag_key})

                        try:
                            client.delete_tags(
                                Resources=[prefix_list_id],
                                Tags=tags_to_delete,
                                aws_retry=True,
                            )
                        except Exception as e:
                            module.fail_json_aws(
                                e,
                                msg=(
                                    "Unable to remove tags from EC2 VPC managed "
                                    f"prefix list {prefix_list_id}"
                                ),
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
                                msg=(
                                    "Unable to tag EC2 VPC managed prefix list "
                                    f"{prefix_list_id}"
                                ),
                            )

                    current = dict(current)
                    current_tags = boto3_tag_list_to_ansible_dict(
                        current.get("Tags", [])
                    )
                    for tag_key in tag_keys_to_unset:
                        current_tags.pop(tag_key, None)
                    current_tags.update(tags_to_set)
                    current["Tags"] = ansible_dict_to_boto3_tag_list(current_tags)
        elif changed and module.check_mode:
            current = dict(current)
            current.update(
                snake_dict_to_camel_dict(desired_prefix_list, capitalize_first=True)
            )
            if tags is not None:
                current["Tags"] = ansible_dict_to_boto3_tag_list(tags)
            current_entries = desired_entries

    prefix_list = boto3_resource_to_ansible_dict(
        current or {}, transform_tags=True, force_tags=False
    )
    if current_entries is not None:
        prefix_list["entries"] = boto3_resource_list_to_ansible_dict(
            current_entries, transform_tags=False, force_tags=False
        )

    result = {
        "changed": changed,
        "name": name,
        "prefix_list": prefix_list,
        "state": "present",
    }
    prefix_list_id = (current or {}).get("PrefixListId")

    if prefix_list_id:
        result["prefix_list_id"] = prefix_list_id
    module.exit_json(**result)


def get_current(client, module):
    prefix_list = get_customer_managed_prefix_list_by_name(client, module)

    if prefix_list is None:
        return None, None

    prefix_list_id = prefix_list.get("PrefixListId")

    try:
        entries = paginated_query_with_retries(
            client,
            "get_managed_prefix_list_entries",
            PrefixListId=prefix_list_id,
        ).get("Entries", [])
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 VPC managed prefix list entries for {prefix_list_id}",
        )

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
            msg=f"Unable to modify EC2 VPC managed prefix list {module.params['name']}",
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
        waiter.wait(
            PrefixListIds=[prefix_list_id],
            WaiterConfig=custom_waiter_config(
                module.params["wait_timeout"],
                default_pause=module.params["wait_delay"],
            ),
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Timed out waiting for EC2 VPC managed prefix list {prefix_list_id}",
        )


def get_customer_managed_prefix_list_by_name(client, module):
    name = module.params["name"]
    filters = ansible_dict_to_boto3_filter_list({"prefix-list-name": name})

    try:
        prefix_lists = paginated_query_with_retries(
            client, "describe_managed_prefix_lists", Filters=filters
        ).get("PrefixLists", [])
    except Exception as e:
        module.fail_json_aws(
            e, msg=f"Unable to describe EC2 VPC managed prefix list {name}"
        )

    matches = []
    for prefix_list in prefix_lists:
        if prefix_list.get("OwnerId") == "AWS":
            continue

        matches.append(prefix_list)

    if len(matches) > 1:
        prefix_list_ids = []
        for prefix_list in matches:
            prefix_list_ids.append(prefix_list.get("PrefixListId"))

        module.fail_json(
            msg=f"More than one EC2 VPC managed prefix list matched name {name}",
            prefix_list_ids=prefix_list_ids,
        )

    return matches[0] if matches else None


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
        normalized_entry = {}
        for field in ("cidr", "description"):
            if entry.get(field) is not None:
                normalized_entry[field] = entry.get(field)

        result.append(normalized_entry)
    return sorted(result, key=lambda entry: json.dumps(entry, sort_keys=True))


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
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 1, "type": "int"},
        "wait_timeout": {"default": 60, "type": "int"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["entries"])],
        supports_check_mode=True,
    )

    if module.params["wait"]:
        if module.params["wait_delay"] < 1:
            module.fail_json(msg="wait_delay must be 1 or greater")

        if module.params["wait_timeout"] < 1:
            module.fail_json(msg="wait_timeout must be 1 or greater")

    state = module.params["state"]
    entries = module.params["entries"]
    tags = module.params["tags"]

    if state == "present":
        if not entries:
            module.fail_json(
                msg="entries must contain at least one item when state=present"
            )

        cidrs = set()
        for entry in entries:
            if entry["cidr"] in cidrs:
                module.fail_json(
                    msg="entries[].cidr values must be unique",
                    cidr=entry["cidr"],
                )
            cidrs.add(entry["cidr"])

    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    method_names = {"describe_managed_prefix_lists"}
    if state == "present":
        method_names.update(
            {
                "create_managed_prefix_list",
                "delete_managed_prefix_list",
                "get_managed_prefix_list_entries",
                "modify_managed_prefix_list",
            }
        )
        if tags is not None:
            method_names.add("create_tags")
            if module.params["purge_tags"]:
                method_names.add("delete_tags")

    if state == "absent":
        method_names.add("delete_managed_prefix_list")

    method_parameters = {}
    for method_name in sorted(method_names):
        try:
            method_parameters[method_name] = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support EC2 {method_name}"
            )

    required_method_parameters = {
        "create_managed_prefix_list": (
            "AddressFamily",
            "Entries",
            "MaxEntries",
            "PrefixListName",
        ),
        "create_tags": ("Resources", "Tags"),
        "delete_managed_prefix_list": ("PrefixListId",),
        "delete_tags": ("Resources", "Tags"),
        "describe_managed_prefix_lists": ("Filters",),
        "get_managed_prefix_list_entries": ("PrefixListId",),
        "modify_managed_prefix_list": (
            "AddEntries",
            "CurrentVersion",
            "MaxEntries",
            "PrefixListId",
            "RemoveEntries",
        ),
    }
    if state == "present" and tags is not None:
        required_method_parameters["create_managed_prefix_list"] += (
            "TagSpecifications",
        )

    for method_name, parameter_names in required_method_parameters.items():
        if method_name not in method_parameters:
            continue

        for parameter_name in set(parameter_names):
            if parameter_name in method_parameters[method_name]:
                continue

            module.fail_json(
                msg=(
                    "Installed botocore does not support EC2 "
                    f"{method_name} parameter {parameter_name}"
                )
            )

    if state == "present":
        ensure_present(client, module)

    if state == "absent":
        ensure_absent(client, module)


if __name__ == "__main__":
    main()
