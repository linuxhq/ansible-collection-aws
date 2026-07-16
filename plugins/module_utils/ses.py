# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_account(client, module):
    try:
        account = client.get_account(aws_retry=True)
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to get AWS Simple Email Service account details"
        )

    account.pop("ResponseMetadata", None)
    return boto3_resource_to_ansible_dict(
        account, transform_tags=False, force_tags=False
    )
