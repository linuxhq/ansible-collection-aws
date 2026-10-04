#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ec2_vpc_prefix_list
version_added: "1.9.0"
short_description: Manage AWS EC2 VPC prefix lists
description:
  - Creates, updates, and deletes EC2 VPC managed prefix lists.
  - Manages prefix list entries idempotently.
  - Entry changes never remove a requested CIDR, even temporarily. Changes that fit in one
    EC2 request are applied atomically; larger changes remove unrequested entries before adding
    new ones, so the prefix list never needs more than O(max_entries) entries.
  - Only prefix lists owned by the current account are managed; AWS-managed prefix lists and
    prefix lists shared from other accounts are ignored. The account is identified with
    C(sts:GetCallerIdentity).
author:
  - Taylor Kimball (@tkimball83)
options:
  address_family:
    description:
      - The address family for the managed prefix list.
      - Changing this value fails without modifying the existing managed prefix list.
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
      - Entries without O(entries[].description) have no description.
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
  max_entries:
    description:
      - The maximum number of entries the managed prefix list can hold.
      - Defaults to the number of O(entries).
      - Set this above the number of O(entries) to leave headroom, so entry changes do not
        resize the prefix list.
      - This must be at least the number of O(entries).
    type: int
    version_added: "2.6.0"
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
  - amazon.aws.tags
attributes:
  check_mode:
    description: Predicts prefix-list, entry, and tag changes without modifying AWS.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
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
    address_family:
      description: The IP address version of the prefix list.
      returned: always
      type: str
      sample: IPv4
    entries:
      description: The prefix list entries.
      returned: when entries are available
      type: list
      elements: dict
      contains:
        cidr:
          description: The CIDR block.
          returned: always
          type: str
          sample: 10.0.0.0/16
        description:
          description: The entry description.
          returned: when the entry has a description
          type: str
    ipam_prefix_list_resolver_sync_enabled:
      description: Whether synchronization with an IPAM prefix list resolver is enabled.
      returned: when returned by EC2
      type: bool
    ipam_prefix_list_resolver_target_id:
      description: The ID of the IPAM prefix list resolver target associated with the prefix list.
      returned: when returned by EC2
      type: str
    max_entries:
      description: The maximum number of entries for the prefix list.
      returned: always
      type: int
      sample: 10
    owner_id:
      description: The ID of the owner of the prefix list.
      returned: when the prefix list exists
      type: str
      sample: "123456789012"
    prefix_list_arn:
      description: The ARN of the prefix list.
      returned: when the prefix list exists
      type: str
      sample: arn:aws:ec2:us-east-1:123456789012:prefix-list/pl-0123456789abcdef0
    prefix_list_id:
      description: The ID of the prefix list.
      returned: when the prefix list exists
      type: str
      sample: pl-0123456789abcdef0
    prefix_list_name:
      description: The name of the prefix list.
      returned: always
      type: str
      sample: example
    state:
      description: The current state of the prefix list.
      returned: when the prefix list exists
      type: str
      sample: create-complete
    state_message:
      description: The state message.
      returned: when returned by EC2
      type: str
    tags:
      description: The prefix list tags.
      returned: when available
      type: dict
    version:
      description: The version of the prefix list.
      returned: when returned by EC2
      type: int
      sample: 1
prefix_list_id:
  description: The managed prefix list identifier.
  returned: when a prefix list exists
  type: str
state:
  description: The requested state of the managed prefix list.
  returned: always
  type: str
"""

import ipaddress
import json

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.iam import get_aws_account_id
from ansible_collections.amazon.aws.plugins.module_utils.iterators import chunks
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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import (
    query_list,
    require_client_methods,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.tags import (
    apply_tag_deltas,
    require_valid_tags,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.wait import (
    require_positive_wait_bounds,
    run_waiter,
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
                "expected": "restore-complete",
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
            {
                "argument": "PrefixLists[0].State",
                "expected": "create-failed",
                "matcher": "path",
                "state": "failure",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "modify-failed",
                "matcher": "path",
                "state": "failure",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "restore-failed",
                "matcher": "path",
                "state": "failure",
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
                "expected": "delete-complete",
                "matcher": "path",
                "state": "success",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "delete-in-progress",
                "matcher": "path",
                "state": "retry",
            },
            {
                "argument": "PrefixLists[0].State",
                "expected": "delete-failed",
                "matcher": "path",
                "state": "failure",
            },
        ],
    },
}

# EC2 accepts at most this many entries in each create, add, or remove request.
MAX_ENTRIES_PER_REQUEST = 100
IN_PROGRESS_STATES = {"create-in-progress", "modify-in-progress", "restore-in-progress"}


def validate_prefix_list(module, prefix_list):
    tags = prefix_list.get("Tags") if isinstance(prefix_list, dict) else None
    if (
        not isinstance(prefix_list, dict)
        or not isinstance(prefix_list.get("AddressFamily"), str)
        or not isinstance(prefix_list.get("MaxEntries"), int)
        or isinstance(prefix_list.get("MaxEntries"), bool)
        or not isinstance(prefix_list.get("OwnerId"), str)
        or not isinstance(prefix_list.get("PrefixListId"), str)
        or not prefix_list["PrefixListId"]
        or not isinstance(prefix_list.get("PrefixListName"), str)
        or not isinstance(prefix_list.get("State"), str)
        or not isinstance(prefix_list.get("Version"), int)
        or isinstance(prefix_list.get("Version"), bool)
        or (tags is not None and not isinstance(tags, list))
        or (
            isinstance(tags, list)
            and any(
                not isinstance(tag, dict)
                or not isinstance(tag.get("Key"), str)
                or not isinstance(tag.get("Value"), str)
                for tag in tags
            )
        )
    ):
        module.fail_json(msg="EC2 returned an invalid managed prefix list")

    return prefix_list


def validate_prefix_list_entries(module, entries):
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("Cidr"), str)
            or not entry["Cidr"]
            or (entry.get("Description") is not None and not isinstance(entry.get("Description"), str))
        ):
            module.fail_json(msg="EC2 returned invalid managed prefix list entries")

    return entries


def create_prefix_list(client, module, owner_id, desired_prefix_list, desired_entries):
    tags = module.params["tags"]
    request = scrub_none_parameters(
        snake_dict_to_camel_dict(
            dict(desired_prefix_list, entries=desired_entries[:MAX_ENTRIES_PER_REQUEST]),
            capitalize_first=True,
        )
    )
    if tags is not None:
        tag_specifications = boto3_tag_specifications(tags, types="prefix-list")

        if tag_specifications is not None:
            request["TagSpecifications"] = tag_specifications

    require_client_methods(
        module,
        client,
        "EC2",
        {"create_managed_prefix_list": tuple(request)},
    )
    try:
        response = client.create_managed_prefix_list(
            **request,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to create EC2 VPC managed prefix list {module.params['name']}",
        )

    prefix_list = validate_prefix_list(
        module,
        response.get("PrefixList") if isinstance(response, dict) else None,
    )

    # EC2 creates at most one request's worth of entries; add the rest once creation completes.
    for batch in chunks(desired_entries[MAX_ENTRIES_PER_REQUEST:], MAX_ENTRIES_PER_REQUEST):
        wait_for_ready_state(client, module, prefix_list["PrefixListId"])
        prefix_list = describe_prefix_list(client, module, prefix_list["PrefixListId"])
        prefix_list = modify_prefix_list(client, module, prefix_list, add_entries=batch)

    if module.params["wait"]:
        wait_for_ready_state(client, module, prefix_list["PrefixListId"])
        return get_current(client, module, owner_id)

    return prefix_list, desired_entries


def delete_prefix_list(client, module, prefix_list_id):
    require_client_methods(
        module,
        client,
        "EC2",
        {"delete_managed_prefix_list": ("PrefixListId",)},
    )
    try:
        client.delete_managed_prefix_list(
            PrefixListId=prefix_list_id,
            aws_retry=True,
        )
    except is_boto3_error_code("InvalidPrefixListID.NotFound"):
        return
    except (BotoCoreError, ClientError) as e:
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


def ensure_absent(client, module, owner_id):
    current = get_customer_managed_prefix_list_by_name(client, module, owner_id)

    state = (current or {}).get("State")
    changed = current is not None and state != "delete-in-progress"
    prefix_list_id = (current or {}).get("PrefixListId")

    if state == "delete-in-progress" and module.params["wait"] and not module.check_mode:
        wait_for_prefix_list_state(client, module, prefix_list_id, "managed_prefix_list_deleted")
    elif changed and not module.check_mode:
        if state in {
            "create-in-progress",
            "modify-in-progress",
            "restore-in-progress",
        }:
            wait_for_ready_state(client, module, prefix_list_id)

        delete_prefix_list(client, module, prefix_list_id)

    result = {
        "changed": changed,
        "name": module.params["name"],
        "state": "absent",
    }
    if prefix_list_id:
        result["prefix_list_id"] = prefix_list_id

    module.exit_json(**result)


def ensure_present(client, module, owner_id):
    name = module.params["name"]
    tags = module.params["tags"]
    purge_tags = module.params["purge_tags"]
    wait = module.params["wait"]
    current, current_entries = get_current(client, module, owner_id)
    if (current or {}).get("State") == "delete-in-progress":
        if module.check_mode:
            current = None
        else:
            wait_for_prefix_list_state(
                client,
                module,
                current.get("PrefixListId"),
                "managed_prefix_list_deleted",
            )
            return ensure_present(client, module, owner_id)

    if (current or {}).get("State") == "create-failed":
        module.fail_json(
            msg=(
                f"EC2 VPC managed prefix list {current['PrefixListId']} failed to create. "
                "Remove it with state=absent before creating it again."
            )
        )

    desired_entries = comparable_entries(module.params["entries"])

    changed = current is None

    desired_prefix_list = {
        "address_family": module.params["address_family"],
        "max_entries": module.params.get("max_entries") or len(desired_entries),
        "prefix_list_name": name,
    }

    if current is None:
        if not module.check_mode:
            current, current_entries = create_prefix_list(
                client,
                module,
                owner_id,
                desired_prefix_list,
                desired_entries,
            )
        else:
            current = snake_dict_to_camel_dict(desired_prefix_list, capitalize_first=True)
            if tags is not None:
                current["Tags"] = ansible_dict_to_boto3_tag_list(tags)

            current_entries = desired_entries
    else:
        current_prefix_list = comparable_prefix_list(current)
        current_entries = comparable_entries(current_entries)
        entries_changed = current_entries != desired_entries

        resource_changed = current_prefix_list != desired_prefix_list
        address_family_changed = current_prefix_list["address_family"] != desired_prefix_list["address_family"]
        if address_family_changed:
            module.fail_json(
                msg=(
                    "address_family cannot be changed for an existing EC2 VPC managed prefix list. "
                    "The existing prefix list has not been modified."
                )
            )

        changed = bool(entries_changed or resource_changed)
        tags_to_set, tag_keys_to_unset = ({}, [])
        if tags is not None:
            tags_to_set, tag_keys_to_unset = compare_aws_tags(
                boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
                tags,
                purge_tags=purge_tags,
            )

        changed = bool(changed or tags_to_set or tag_keys_to_unset)

        if (changed or wait) and not module.check_mode and current.get("State") in IN_PROGRESS_STATES:
            wait_for_ready_state(client, module, current.get("PrefixListId"))
            return ensure_present(client, module, owner_id)

        if changed and not module.check_mode:
            if entries_changed or resource_changed:
                current, current_entries = update_prefix_list(
                    client,
                    module,
                    owner_id,
                    current,
                    current_entries,
                    desired_entries,
                    desired_prefix_list["max_entries"],
                )
                current_prefix_list = comparable_prefix_list(current)
                if wait and current_prefix_list != desired_prefix_list:
                    module.fail_json(
                        msg=(
                            "EC2 VPC managed prefix list does not match the requested configuration after updating. "
                            "The prefix list has not been deleted; inspect the current configuration before retrying."
                        ),
                        current=current_prefix_list,
                        desired=desired_prefix_list,
                    )

            if current is not None and tags is not None:
                tags_to_set, tag_keys_to_unset = compare_aws_tags(
                    boto3_tag_list_to_ansible_dict(current.get("Tags", [])),
                    tags,
                    purge_tags=purge_tags,
                )
                prefix_list_id = current.get("PrefixListId")

                if prefix_list_id:
                    if tag_keys_to_unset:
                        require_client_methods(
                            module,
                            client,
                            "EC2",
                            {"delete_tags": ("Resources", "Tags")},
                        )
                        try:
                            client.delete_tags(
                                Resources=[prefix_list_id],
                                Tags=[{"Key": key} for key in tag_keys_to_unset],
                                aws_retry=True,
                            )
                        except (BotoCoreError, ClientError) as e:
                            module.fail_json_aws(
                                e,
                                msg=f"Unable to remove tags from EC2 VPC managed prefix list {prefix_list_id}",
                            )

                    if tags_to_set:
                        require_client_methods(
                            module,
                            client,
                            "EC2",
                            {"create_tags": ("Resources", "Tags")},
                        )
                        try:
                            client.create_tags(
                                Resources=[prefix_list_id],
                                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                                aws_retry=True,
                            )
                        except (BotoCoreError, ClientError) as e:
                            module.fail_json_aws(
                                e,
                                msg=f"Unable to tag EC2 VPC managed prefix list {prefix_list_id}",
                            )

                    current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)
        elif changed and module.check_mode:
            current = dict(current)
            current.update(snake_dict_to_camel_dict(desired_prefix_list, capitalize_first=True))
            if tags is not None:
                current = apply_tag_deltas(current, tags_to_set, tag_keys_to_unset)

            current_entries = desired_entries

    prefix_list = boto3_resource_to_ansible_dict(current or {}, transform_tags=True, force_tags=False)
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


def get_current(client, module, owner_id):
    prefix_list = get_customer_managed_prefix_list_by_name(client, module, owner_id)

    if prefix_list is None:
        return None, None

    if prefix_list.get("State") == "delete-in-progress":
        return prefix_list, None

    prefix_list_id = prefix_list.get("PrefixListId")

    require_client_methods(
        module,
        client,
        "EC2",
        {
            "get_managed_prefix_list_entries": (
                "MaxResults",
                "NextToken",
                "PrefixListId",
            )
        },
    )
    entries = validate_prefix_list_entries(
        module,
        query_list(
            module,
            client,
            "get_managed_prefix_list_entries",
            "Entries",
            f"Unable to get EC2 VPC managed prefix list entries for {prefix_list_id}",
            PrefixListId=prefix_list_id,
        ),
    )

    return prefix_list, entries


def update_prefix_list(client, module, owner_id, current, current_entries, desired_entries, max_entries):
    """Converge entries and size without ever removing a requested CIDR."""
    current_cidrs = {entry["cidr"] for entry in current_entries}
    desired_cidrs = {entry["cidr"] for entry in desired_entries}
    # Adding an existing CIDR replaces its description, so description changes are additions only.
    add_entries = [entry for entry in desired_entries if entry not in current_entries]
    remove_entries = [{"cidr": cidr} for cidr in sorted(current_cidrs - desired_cidrs)]

    # EC2 checks MaxEntries after each request. One request applies everything atomically. Batches
    # remove only unrequested CIDRs before adding, so the list never holds more than its current or
    # requested entries and never needs more room than max_entries.
    if len(add_entries) <= MAX_ENTRIES_PER_REQUEST and len(remove_entries) <= MAX_ENTRIES_PER_REQUEST:
        entry_steps = [{"add_entries": add_entries or None, "remove_entries": remove_entries or None}]
    else:
        entry_steps = [{"remove_entries": batch} for batch in chunks(remove_entries, MAX_ENTRIES_PER_REQUEST)]
        entry_steps += [{"add_entries": batch} for batch in chunks(add_entries, MAX_ENTRIES_PER_REQUEST)]

    steps = []
    size = current["MaxEntries"]
    if max_entries > size:
        steps.append({"max_entries": max_entries})
        size = max_entries

    if add_entries or remove_entries:
        steps.extend(entry_steps)

    if size != max_entries:
        steps.append({"max_entries": max_entries})

    for step in steps[:-1]:
        modify_prefix_list(client, module, current, **step)
        wait_for_ready_state(client, module, current["PrefixListId"])
        current = describe_prefix_list(client, module, current["PrefixListId"])

    current = modify_prefix_list(client, module, current, **steps[-1])
    if not module.params["wait"]:
        return current, desired_entries

    wait_for_ready_state(client, module, current["PrefixListId"])
    return get_current(client, module, owner_id)


def describe_prefix_list(client, module, prefix_list_id):
    prefix_lists = query_list(
        module,
        client,
        "describe_managed_prefix_lists",
        "PrefixLists",
        f"Unable to describe EC2 VPC managed prefix list {prefix_list_id}",
        PrefixListIds=[prefix_list_id],
    )
    if len(prefix_lists) != 1:
        module.fail_json(msg=f"EC2 did not return managed prefix list {prefix_list_id}")

    return validate_prefix_list(module, prefix_lists[0])


def modify_prefix_list(client, module, current, **kwargs):
    request = {
        "prefix_list_id": current.get("PrefixListId"),
    }
    if "add_entries" in kwargs or "remove_entries" in kwargs:
        request["current_version"] = current.get("Version")

    request.update(kwargs)
    request = scrub_none_parameters(snake_dict_to_camel_dict(request, capitalize_first=True))

    require_client_methods(
        module,
        client,
        "EC2",
        {"modify_managed_prefix_list": tuple(request)},
    )
    try:
        response = client.modify_managed_prefix_list(
            **request,
            aws_retry=True,
        )
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to modify EC2 VPC managed prefix list {module.params['name']}",
        )

    return validate_prefix_list(
        module,
        response.get("PrefixList") if isinstance(response, dict) else None,
    )


def wait_for_ready_state(client, module, prefix_list_id):
    wait_for_prefix_list_state(
        client,
        module,
        prefix_list_id,
        "managed_prefix_list_ready",
    )


def wait_for_prefix_list_state(client, module, prefix_list_id, waiter_name):
    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_managed_prefix_lists": ("PrefixListIds",)},
    )
    run_waiter(
        module,
        client,
        EC2_WAITER_MODEL_DATA,
        waiter_name,
        f"Unable to wait for EC2 VPC managed prefix list {prefix_list_id}",
        PrefixListIds=[prefix_list_id],
    )


def get_customer_managed_prefix_list_by_name(client, module, owner_id):
    name = module.params["name"]
    filters = ansible_dict_to_boto3_filter_list({"prefix-list-name": name})

    prefix_lists = query_list(
        module,
        client,
        "describe_managed_prefix_lists",
        "PrefixLists",
        f"Unable to describe EC2 VPC managed prefix list {name}",
        Filters=filters,
    )

    matches = []
    for prefix_list in prefix_lists:
        validate_prefix_list(module, prefix_list)
        # Skip AWS-managed lists and lists shared from other accounts, which cannot be modified.
        if prefix_list.get("OwnerId") != owner_id or prefix_list.get("State") == "delete-complete":
            continue

        matches.append(prefix_list)

    if len(matches) > 1:
        prefix_list_ids = [prefix_list.get("PrefixListId") for prefix_list in matches]

        module.fail_json(
            msg=f"More than one EC2 VPC managed prefix list matched name {name}",
            prefix_list_ids=prefix_list_ids,
        )

    return matches[0] if matches else None


def comparable_prefix_list(prefix_list):
    normalized = boto3_resource_to_ansible_dict(prefix_list, transform_tags=False, force_tags=False)
    return {
        "address_family": normalized.get("address_family"),
        "max_entries": normalized.get("max_entries"),
        "prefix_list_name": normalized.get("prefix_list_name"),
    }


def comparable_entries(entries):
    normalized_entries = boto3_resource_list_to_ansible_dict(entries, transform_tags=False, force_tags=False)
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
        "max_entries": {"type": "int"},
        "name": {"required": True, "type": "str"},
        "purge_tags": {"default": True, "type": "bool"},
        "state": {
            "choices": ["absent", "present"],
            "default": "present",
            "type": "str",
        },
        "tags": {"aliases": ["resource_tags"], "type": "dict"},
        "wait": {"default": True, "type": "bool"},
        "wait_delay": {"default": 1, "type": "int"},
        "wait_timeout": {"default": 60, "type": "int"},
    }

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        required_if=[("state", "present", ["entries"])],
        supports_check_mode=True,
    )

    state = module.params["state"]
    require_positive_wait_bounds(module, always=True)

    entries = module.params["entries"]
    tags = module.params["tags"]

    if state == "present":
        if not entries:
            module.fail_json(msg="entries must contain at least one item when state=present")

        max_entries = module.params.get("max_entries")
        if max_entries is not None and max_entries < len(entries):
            module.fail_json(msg="max_entries must be at least the number of entries")

        cidrs = set()
        for entry in entries:
            if len(entry.get("description") or "") > 255:
                module.fail_json(msg="entries[].description must contain at most 255 characters")

            try:
                cidr = ipaddress.ip_network(entry["cidr"])
            except ValueError:
                module.fail_json(msg=f"entries[].cidr must be a valid CIDR: {entry['cidr']}")

            if cidr.version != int(module.params["address_family"][-1]):
                module.fail_json(
                    msg=(
                        f"entries[].cidr must match address_family "
                        f"{module.params['address_family']}: {entry['cidr']}"
                    )
                )

            entry["cidr"] = str(cidr)
            if entry["cidr"] in cidrs:
                module.fail_json(
                    msg="entries[].cidr values must be unique",
                    cidr=entry["cidr"],
                )

            cidrs.add(entry["cidr"])

    require_valid_tags(module, tags if state == "present" else None, 50, key_max=127)
    client = module.client("ec2", retry_decorator=AWSRetry.jittered_backoff())

    require_client_methods(
        module,
        client,
        "EC2",
        {"describe_managed_prefix_lists": ("Filters", "MaxResults", "NextToken")},
    )

    owner_id = get_aws_account_id(module)

    if state == "present":
        ensure_present(client, module, owner_id)

    if state == "absent":
        ensure_absent(client, module, owner_id)


if __name__ == "__main__":
    main()
