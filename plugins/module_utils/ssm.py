# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)


def association_overview(overview, count_key="AssociationStatusAggregatedCount"):
    # The aggregated count is keyed by association status names, which are data rather than field names.
    if not isinstance(overview, dict):
        return overview

    return camel_dict_to_snake_dict(overview, ignore_list=[count_key])


def list_ssm_tags(module, client, resource_type, resource_id, description, changed=False, missing_ok=False):
    """Return an SSM resource's tag list, or None when missing_ok is set and the resource no longer exists.

    changed reports whether the resource was already modified, for failure results.
    """
    try:
        response = client.list_tags_for_resource(
            ResourceType=resource_type,
            ResourceId=resource_id,
            aws_retry=True,
        )
    except is_boto3_error_code("InvalidResourceId") as e:
        if missing_ok:
            return None

        module.fail_json_aws(e, changed=changed, msg=f"Unable to list tags for {description} {resource_id}")
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, changed=changed, msg=f"Unable to list tags for {description} {resource_id}")

    tags = response.get("TagList", []) if isinstance(response, dict) else None
    if not isinstance(tags, list) or any(not isinstance(tag, dict) for tag in tags):
        module.fail_json(changed=changed, msg=f"Unexpected response while listing tags for {description} {resource_id}")

    return tags
