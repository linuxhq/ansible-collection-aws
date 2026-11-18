# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.tagging import boto3_tag_list_to_ansible_dict

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import query_list


def get_resource_tags(client, module, resource, description):
    """Return a WAFv2 resource's tags, or None when it was deleted after it was listed."""
    identifier = f"{resource['Name']}/{resource['Id']}"
    request = {"ResourceARN": resource["ARN"]}
    tags = []
    while True:
        try:
            response = client.list_tags_for_resource(**request, aws_retry=True)
        except is_boto3_error_code("WAFNonexistentItemException"):
            return None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to list tags for AWS WAFv2 {description} {identifier}")

        tags.extend(response.get("TagInfoForResource", {}).get("TagList", []))
        if not response.get("NextMarker"):
            return boto3_tag_list_to_ansible_dict(tags)

        request["NextMarker"] = response["NextMarker"]


def get_resources_with_tags(client, module, summaries, method, result_key, description, scope):
    """Return (resource, tags) for each listed summary, skipping resources deleted after they were listed."""
    resources = []
    for summary in summaries:
        identifier = f"{summary['Name']}/{summary['Id']}"
        try:
            response = getattr(client, method)(
                Id=summary["Id"],
                Name=summary["Name"],
                Scope=scope,
                aws_retry=True,
            )
        except is_boto3_error_code("WAFNonexistentItemException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to get AWS WAFv2 {description} {identifier}")

        resource = response[result_key]
        tags = get_resource_tags(client, module, resource, description)
        if tags is None:
            continue

        resources.append((resource, tags))

    return resources


def list_resource_summaries(client, module, method, result_key, description, scope):
    """Return the WAFv2 resource summaries matching the id and name options; both together skip the listing."""
    target_id = module.params["id"]
    target_name = module.params["name"]
    if target_id and target_name:
        return [{"Id": target_id, "Name": target_name}]

    response_summaries = query_list(
        module,
        client,
        method,
        result_key,
        f"Unable to list AWS WAFv2 {description} for {scope}",
        Scope=scope,
        Limit=100,
    )
    summaries = []
    for summary in response_summaries:
        if target_id and summary["Id"] != target_id:
            continue

        if target_name and summary["Name"] != target_name:
            continue

        summaries.append(summary)
        if target_id or target_name:
            break

    return summaries
