# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)


def quota_from_response(module, response, description, service_code, quota_code, context_id=None, resource_scope=False):
    if not isinstance(response, dict) or not isinstance(response.get("Quota"), dict) or not response["Quota"]:
        module.fail_json(msg=f"AWS Service Quotas returned an invalid {description} response")

    quota = response["Quota"]
    for key, expected in (("ServiceCode", service_code), ("QuotaCode", quota_code)):
        if key in quota and quota[key] != expected:
            module.fail_json(msg=f"AWS Service Quotas returned a mismatched quota for {service_code}/{quota_code}")

    quota_context = quota.get("QuotaContext")
    if quota_context is not None and not isinstance(quota_context, dict):
        module.fail_json(msg=f"AWS Service Quotas returned an invalid quota context for {service_code}/{quota_code}")

    if context_id and (quota_context is None or quota_context.get("ContextId") != context_id):
        module.fail_json(msg=f"AWS Service Quotas returned a mismatched quota context for {service_code}/{quota_code}")

    if resource_scope and (quota_context or {}).get("ContextScope", "RESOURCE") != "RESOURCE":
        module.fail_json(msg=f"AWS Service Quotas returned a mismatched quota context for {service_code}/{quota_code}")

    return quota


def get_quota(client, module, service_code, quota_code, context_id=None):
    """Return the applied quota, falling back to the resource-scope and default quotas; return None when missing.

    A context without its own applied value uses the quota that applies to every resource in the scope.
    """
    identifier = f"{service_code}/{quota_code}" + (f" for {context_id}" if context_id else "")
    request = {"QuotaCode": quota_code, "ServiceCode": service_code}
    lookups = [
        (client.get_service_quota, "service quota", request, None),
        (client.get_aws_default_service_quota, "default service quota", request, None),
    ]
    if context_id:
        lookups.insert(0, (client.get_service_quota, "service quota", dict(request, ContextId=context_id), context_id))

    for method, description, lookup_request, lookup_context_id in lookups:
        try:
            response = method(**lookup_request, aws_retry=True)
        except is_boto3_error_code("NoSuchResourceException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(e, msg=f"Unable to get AWS {description} {identifier}")

        return quota_from_response(
            module,
            response,
            description,
            service_code,
            quota_code,
            lookup_context_id,
            resource_scope=bool(context_id) and not lookup_context_id,
        )

    return None


def quota_to_ansible_dict(quota):
    return boto3_resource_to_ansible_dict(
        quota,
        transform_tags=False,
        force_tags=False,
        nested_transforms={
            "UsageMetric": lambda metric: camel_dict_to_snake_dict(metric, ignore_list=["MetricDimensions"]),
        },
    )
