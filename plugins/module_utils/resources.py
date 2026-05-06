#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def aws_resource_list_to_snake_dicts(
    resources, ignore_list=None, nested_transforms=None
):
    return boto3_resource_list_to_ansible_dict(
        resources,
        transform_tags=False,
        force_tags=False,
        ignore_list=ignore_list,
        nested_transforms=nested_transforms,
    )


def aws_resource_to_snake_dict(resource, ignore_list=None, nested_transforms=None):
    return boto3_resource_to_ansible_dict(
        resource,
        transform_tags=False,
        force_tags=False,
        ignore_list=ignore_list,
        nested_transforms=nested_transforms,
    )
