#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def list_wafv2_summaries(client, module, scope, operation, result_key, error_message):
    summaries = []
    next_marker = None
    list_wafv2_resources = AWSRetry.jittered_backoff()(getattr(client, operation))

    try:
        while True:
            request = {"Scope": scope}
            if next_marker:
                request["NextMarker"] = next_marker

            response = list_wafv2_resources(**request)
            summaries.extend(response.get(result_key, []))
            next_marker = response.get("NextMarker")
            if not next_marker:
                break
    except Exception as e:
        module.fail_json_aws(e, msg=error_message)

    return summaries


def normalize_wafv2_resource(resource):
    return boto3_resource_to_ansible_dict(resource, force_tags=False)
