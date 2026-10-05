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
    identifier = f"{resource.get('Name')}/{resource.get('Id')}"
    request = {"ResourceARN": resource.get("ARN")}
    tags = []
    while True:
        try:
            response = client.list_tags_for_resource(**request, aws_retry=True)
        except is_boto3_error_code("WAFNonexistentItemException"):
            return None
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to list tags for AWS WAFv2 {description} {identifier}")

        tag_info = response.get("TagInfoForResource", {}) if isinstance(response, dict) else None
        tag_list = tag_info.get("TagList", []) if isinstance(tag_info, dict) else None
        if not isinstance(tag_list, list) or any(not isinstance(tag, dict) for tag in tag_list):
            module.fail_json(msg=f"Unexpected response while listing tags for AWS WAFv2 {description} {identifier}")

        tags.extend(tag_list)
        if not response.get("NextMarker"):
            return boto3_tag_list_to_ansible_dict(tags)

        request["NextMarker"] = response["NextMarker"]


def require_lookup_params(module):
    """Validate the id, name, and scope options shared by WAFv2 info modules before any AWS call."""
    if module.params["id"] == "":
        module.fail_json(msg="id must not be empty")

    if module.params["name"] == "":
        module.fail_json(msg="name must not be empty")

    if module.params["scope"] == "cloudfront" and module.region != "us-east-1":
        module.fail_json(msg=f"scope cloudfront requires the us-east-1 region, not {module.region}")


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
    if not isinstance(response_summaries, list):
        module.fail_json(msg=f"Unexpected response while listing AWS WAFv2 {description} for {scope}")

    summaries = []
    for summary in response_summaries:
        summary_id = summary.get("Id") if isinstance(summary, dict) else None
        summary_name = summary.get("Name") if isinstance(summary, dict) else None
        if target_id and summary_id != target_id:
            continue

        if target_name and summary_name != target_name:
            continue

        if not isinstance(summary_id, str) or not summary_id:
            module.fail_json(msg=f"Unexpected response while listing AWS WAFv2 {description} for {scope}; invalid ID")

        if not isinstance(summary_name, str) or not summary_name:
            module.fail_json(msg=f"Unexpected response while listing AWS WAFv2 {description} for {scope}; invalid name")

        summaries.append(summary)
        if target_id or target_name:
            break

    return summaries
