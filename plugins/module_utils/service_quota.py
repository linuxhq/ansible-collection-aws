#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def get_service_quota(client, module, quota_code=None, service_code=None):
    quota_code = quota_code or module.params["quota_code"]
    service_code = service_code or module.params["service_code"]

    get_service_quota = AWSRetry.jittered_backoff()(client.get_service_quota)
    try:
        response = get_service_quota(
            QuotaCode=quota_code,
            ServiceCode=service_code,
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                f"Unable to get AWS service quota {quota_code} "
                f"for service {service_code}"
            ),
        )
    return response.get("Quota", {})


def normalize_quota(quota):
    return boto3_resource_to_ansible_dict(quota, force_tags=False)
