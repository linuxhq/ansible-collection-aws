# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
)


def apply_tag_deltas(resource, tags_to_set, tag_keys_to_unset):
    updated = dict(resource)
    tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)

    tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return updated


def reconcile_arn_tags(
    module, client, resource_arn, tags_to_set, tag_keys_to_unset, description
):
    if tag_keys_to_unset:
        try:
            client.untag_resource(
                ResourceArn=resource_arn,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to remove tags from {description} {resource_arn}"
            )

    if tags_to_set:
        try:
            client.tag_resource(
                ResourceArn=resource_arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
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
        except Exception as e:
            module.fail_json_aws(
                e, msg=f"Unable to remove tags from {description} {resource_id}"
            )

    if tags_to_set:
        try:
            client.add_tags_to_resource(
                ResourceType=resource_type,
                ResourceId=resource_id,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except Exception as e:
            module.fail_json_aws(e, msg=f"Unable to tag {description} {resource_id}")
