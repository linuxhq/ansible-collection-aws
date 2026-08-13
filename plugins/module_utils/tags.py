# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.text.converters import to_native

from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
)


def require_valid_tags(module, tags, max_tags, key_max=128):
    if tags is None:
        return
    normalized = {to_native(key): to_native(value) for key, value in tags.items()}
    if len(normalized) != len(tags):
        module.fail_json(msg="tag keys must be unique after string normalization")
    tags.clear()
    tags.update(normalized)
    if len(tags) > max_tags:
        module.fail_json(msg=f"tags must contain at most {max_tags} entries")
    if any(not 1 <= len(key) <= key_max or len(value) > 256 for key, value in tags.items()):
        module.fail_json(msg=(f"tag keys must contain 1 to {key_max} characters and values " "at most 256 characters"))


def apply_tag_deltas(resource, tags_to_set, tag_keys_to_unset):
    updated = dict(resource)
    tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)

    tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return updated


def reconcile_arn_tags(module, client, resource_arn, tags_to_set, tag_keys_to_unset, description):
    if tag_keys_to_unset:
        try:
            client.untag_resource(
                ResourceArn=resource_arn,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to remove tags from {description} {resource_arn}")

    if tags_to_set:
        try:
            client.tag_resource(
                ResourceArn=resource_arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to tag {description} {resource_arn}")


def reconcile_ssm_tags(
    module,
    client,
    resource_type,
    resource_id,
    tags_to_set,
    tag_keys_to_unset,
    description,
):
    if tag_keys_to_unset:
        try:
            client.remove_tags_from_resource(
                ResourceType=resource_type,
                ResourceId=resource_id,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to remove tags from {description} {resource_id}")

    if tags_to_set:
        try:
            client.add_tags_to_resource(
                ResourceType=resource_type,
                ResourceId=resource_id,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to tag {description} {resource_id}")
