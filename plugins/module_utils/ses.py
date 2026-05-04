#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_account(client, module):
    get_account = AWSRetry.jittered_backoff()(client.get_account)
    try:
        response = get_account()
    except Exception as e:
        module.fail_json_aws(
            e, msg="Unable to get AWS Simple Email Service account details"
        )
    return response


def normalize_account(account):
    return boto3_resource_to_ansible_dict(account, force_tags=False)
