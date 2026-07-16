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
