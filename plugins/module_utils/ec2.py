#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def get_account_level(client, module):
    get_instance_metadata_defaults = AWSRetry.jittered_backoff()(
        client.get_instance_metadata_defaults
    )
    try:
        response = get_instance_metadata_defaults()
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get EC2 instance metadata defaults")
    return response.get("AccountLevel", {})


def get_prefix_list_entries(client, module, prefix_list_id):
    try:
        response = paginated_query_with_retries(
            client,
            "get_managed_prefix_list_entries",
            PrefixListId=prefix_list_id,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 VPC managed prefix list entries for {prefix_list_id}",
        )

    return boto3_resource_list_to_ansible_dict(
        response.get("Entries", []),
        force_tags=False,
    )


def get_serial_console_access(client, module):
    get_serial_console_access_status = AWSRetry.jittered_backoff()(
        client.get_serial_console_access_status
    )
    try:
        response = get_serial_console_access_status()
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to get EC2 serial console access status")

    status = {
        "ManagedBy": response.get("ManagedBy"),
        "SerialConsoleAccessEnabled": response.get("SerialConsoleAccessEnabled"),
    }
    return {key: value for key, value in status.items() if value is not None}


def list_prefix_lists(client, module):
    try:
        response = paginated_query_with_retries(client, "describe_managed_prefix_lists")
    except Exception as e:
        module.fail_json_aws(e, msg="Unable to describe EC2 VPC managed prefix lists")

    return response.get("PrefixLists", [])


def normalize_account_level(account_level):
    return boto3_resource_to_ansible_dict(account_level, force_tags=False)


def normalize_prefix_list(prefix_list, entries=None):
    normalized = boto3_resource_to_ansible_dict(prefix_list or {}, force_tags=False)
    if entries is not None:
        normalized["entries"] = entries
    return normalized


def normalize_serial_console_access(serial_console_access):
    return boto3_resource_to_ansible_dict(serial_console_access, force_tags=False)
