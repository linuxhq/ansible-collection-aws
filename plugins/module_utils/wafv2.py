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
