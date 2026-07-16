# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_instance_metadata_defaults(client, module):
    try:
        return boto3_resource_to_ansible_dict(
            client.get_instance_metadata_defaults(aws_retry=True).get(
                "AccountLevel", {}
            ),
            transform_tags=False,
            force_tags=False,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get EC2 instance metadata defaults in region {module.region}",
        )
