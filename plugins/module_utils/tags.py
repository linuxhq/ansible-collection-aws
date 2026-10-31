# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import unicodedata

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.text.converters import to_native

from ansible_collections.amazon.aws.plugins.module_utils.iterators import chunks
from ansible_collections.amazon.aws.plugins.module_utils.tagging import (
    ansible_dict_to_boto3_tag_list,
    boto3_tag_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods

# EC2 documents up to 1000 resource IDs per CreateTags or DeleteTags call, but
# returns InternalError above 100 flow log IDs.
MAX_EC2_TAG_RESOURCES_PER_REQUEST = 100
# Besides letters, separators, and numbers, the SSM, IAM, and ACM tag pattern [\p{L}\p{Z}\p{N}_.:/=+\-@] allows these.
# EKS, Global Accelerator, Notifications Contacts, Pinpoint SMS Voice V2, and Route 53 Resolver enforce the same
# characters without a model pattern.
RESTRICTED_TAG_SYMBOLS = "_.:/=+-@"
# EC2 treats a tag key or a prefix list entry description made only of these characters as blank: it rejects the key
# and stores no description. They are the str.isspace() characters except \x0b, \x0c, and \x1c-\x1f, which EC2 rejects
# anywhere as invalid XML.
EC2_BLANK_CHARACTERS = (
    "\t\n\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)
# EC2 stores a tag value made only of these characters as "", and every other value as sent.
EC2_BLANK_TAG_VALUE_CHARACTERS = " \t\n\r"


def require_valid_tags(module, tags, max_tags, restricted_characters=False, ec2=False):
    """Fail unless tags are non-null, unique as strings, at most max_tags, and within the AWS lengths.

    Keys and values are normalized to strings in place. restricted_characters also requires the characters of the SSM,
    IAM, and ACM tag pattern, which those services, EKS, Global Accelerator, Notifications Contacts, Pinpoint SMS Voice
    V2, and Route 53 Resolver enforce on every tag write. ec2 also rejects the blank keys EC2 refuses, and replaces each
    value EC2 stores as "" with "", so requests, comparisons, and check-mode results use the stored value.
    """
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
    # AWS reserves the aws: prefix, and those tags do not count against the per-resource limit.
    if sum(not key.lower().startswith("aws:") for key in tags) > max_tags:
        module.fail_json(msg=f"tags must contain at most {max_tags} entries")

    if any(not 1 <= len(key) <= 128 or len(value) > 256 for key, value in tags.items()):
        module.fail_json(msg="tag keys must contain 1 to 128 characters and values at most 256 characters")

    if ec2:
        if any(not key.strip(EC2_BLANK_CHARACTERS) for key in tags):
            module.fail_json(msg="tag keys must not be blank")

        tags.update({key: "" for key, value in tags.items() if not value.strip(EC2_BLANK_TAG_VALUE_CHARACTERS)})

    # Python re has no \p{..} classes, so the Unicode general category stands in for \p{L}, \p{N}, and \p{Z}.
    if restricted_characters and any(
        unicodedata.category(char)[0] not in "LNZ" and char not in RESTRICTED_TAG_SYMBOLS
        for key, value in tags.items()
        for char in key + value
    ):
        module.fail_json(msg="tag keys and values must contain only letters, numbers, spaces, and _ . : / = + - @")


def require_resulting_tag_limit(module, current_tags, tags_to_set, tag_keys_to_unset, max_tags, description):
    """Fail before any write when applying the tag deltas to current_tags would exceed max_tags."""
    final_tags = updated_tags(current_tags, tags_to_set, tag_keys_to_unset)
    # AWS reserves the aws: prefix, and those tags do not count against the per-resource limit.
    if sum(not key.lower().startswith("aws:") for key in final_tags) > max_tags:
        module.fail_json(msg=f"The resulting {description} tags must contain at most {max_tags} entries")


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
    tags = updated_tags(boto3_tag_list_to_ansible_dict(updated.get("Tags", [])), tags_to_set, tag_keys_to_unset)
    updated["Tags"] = ansible_dict_to_boto3_tag_list(tags)
    return updated


def updated_tags(current_tags, tags_to_set, tag_keys_to_unset):
    """Return a copy of the current_tags dictionary with the tag deltas applied."""
    tags = dict(current_tags)
    for tag_key in tag_keys_to_unset:
        tags.pop(tag_key, None)

    tags.update(tags_to_set)
    return tags


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


def ssm_tag_methods(tags, purge_tags):
    """Return the SSM tag methods a tags option needs, in the form require_client_methods accepts."""
    methods = {}
    if tags is None:
        return methods

    methods["list_tags_for_resource"] = ("ResourceId", "ResourceType")
    if tags:
        methods["add_tags_to_resource"] = ("ResourceId", "ResourceType", "Tags")

    if purge_tags:
        methods["remove_tags_from_resource"] = ("ResourceId", "ResourceType", "TagKeys")

    return methods


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

    batches = list(chunks(resource_ids, MAX_EC2_TAG_RESOURCES_PER_REQUEST))

    if tag_keys_to_unset:
        for batch in batches:
            try:
                client.delete_tags(
                    Resources=batch,
                    Tags=[{"Key": key} for key in tag_keys_to_unset],
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(
                    e, changed=changed, msg=f"Unable to remove tags from {description} {', '.join(batch)}"
                )

            changed = True

    if tags_to_set:
        for batch in batches:
            try:
                client.create_tags(
                    Resources=batch,
                    Tags=ansible_dict_to_boto3_tag_list(tags_to_set),
                    aws_retry=True,
                )
            except (BotoCoreError, ClientError) as e:
                module.fail_json_aws(e, changed=changed, msg=f"Unable to tag {description} {', '.join(batch)}")

            changed = True
