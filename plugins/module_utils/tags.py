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

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods


def require_valid_tags(module, tags, max_tags, key_max=128):
    if tags is None:
        return

    # to_native would otherwise turn a null into the literal string "None".
    if any(key is None or value is None for key, value in tags.items()):
        module.fail_json(msg="tag keys and values must not be null")

    normalized = {to_native(key): to_native(value) for key, value in tags.items()}
    if len(normalized) != len(tags):
        module.fail_json(msg="tag keys must be unique after string normalization")

    tags.clear()
    tags.update(normalized)
    if len(tags) > max_tags:
        module.fail_json(msg=f"tags must contain at most {max_tags} entries")

    if any(not 1 <= len(key) <= key_max or len(value) > 256 for key, value in tags.items()):
        module.fail_json(msg=f"tag keys must contain 1 to {key_max} characters and values at most 256 characters")


def require_valid_tag_list(module, tags, msg, changed=False):
    """Validate an AWS tag list; changed reports whether the resource was already modified, for failure results."""
    if not isinstance(tags, list) or any(
        not isinstance(tag, dict) or not isinstance(tag.get("Key"), str) or not isinstance(tag.get("Value"), str)
        for tag in tags
    ):
        module.fail_json(changed=changed, msg=msg)

    return tags


def apply_tag_deltas(resource, tags_to_set, tag_keys_to_unset):
    updated = dict(resource)
    tags = boto3_tag_list_to_ansible_dict(updated.get("Tags", []))

    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)

    tags.update(tags_to_set)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return updated


def reconcile_arn_tags(module, client, resource_arn, tags_to_set, tag_keys_to_unset, description, changed=False):
    """Reconcile ARN tags; changed reports whether the resource was already modified, for failure results."""
    if tag_keys_to_unset:
        try:
            client.untag_resource(
                ResourceArn=resource_arn,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=changed, msg=f"Unable to remove tags from {description} {resource_arn}")

        changed = True

    if tags_to_set:
        try:
            client.tag_resource(
                ResourceArn=resource_arn,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=changed, msg=f"Unable to tag {description} {resource_arn}")


def reconcile_ssm_tags(
    module,
    client,
    resource_type,
    resource_id,
    tags_to_set,
    tag_keys_to_unset,
    description,
    changed=False,
):
    """Reconcile SSM tags; changed reports whether the resource was already modified, for failure results."""
    if tag_keys_to_unset:
        try:
            client.remove_tags_from_resource(
                ResourceType=resource_type,
                ResourceId=resource_id,
                TagKeys=tag_keys_to_unset,
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=changed, msg=f"Unable to remove tags from {description} {resource_id}")

        changed = True

    if tags_to_set:
        try:
            client.add_tags_to_resource(
                ResourceType=resource_type,
                ResourceId=resource_id,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=changed, msg=f"Unable to tag {description} {resource_id}")


def ec2_tag_methods(tags_to_set, tag_keys_to_unset):
    """Return the EC2 tag methods reconcile_ec2_tags calls, in the form require_client_methods accepts."""
    methods = {}
    if tag_keys_to_unset:
        methods["delete_tags"] = ("Resources", "Tags")

    if tags_to_set:
        methods["create_tags"] = ("Resources", "Tags")

    return methods


def reconcile_ec2_tags(
    module,
    client,
    resource_ids,
    tags_to_set,
    tag_keys_to_unset,
    description,
    changed=False,
    check_sdk=False,
):
    """Reconcile EC2 tags; changed reports whether the resources were already modified, for failure results.

    check_sdk first fails if the installed botocore lacks a tag method this call needs.
    """
    if check_sdk:
        require_client_methods(module, client, "EC2", ec2_tag_methods(tags_to_set, tag_keys_to_unset), changed=changed)

    identifier = ", ".join(resource_ids)

    if tag_keys_to_unset:
        try:
            client.delete_tags(
                Resources=resource_ids,
                Tags=[{"Key": key} for key in tag_keys_to_unset],
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=changed, msg=f"Unable to remove tags from {description} {identifier}")

        changed = True

    if tags_to_set:
        try:
            client.create_tags(
                Resources=resource_ids,
                Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                aws_retry=True,
            )
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, changed=changed, msg=f"Unable to tag {description} {identifier}")
