# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

try:
    from botocore.exceptions import BotoCoreError, ClientError
    from botocore.model import OperationNotFoundError
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)


def get_client_method_output_members(client, method_name):
    operation_name = client.meta.method_to_api_mapping.get(method_name)
    output_shape = client.meta.service_model.operation_model(operation_name).output_shape
    return list(output_shape.members) if output_shape else []


def query_list(module, client, method_name, result_key, error_msg, **kwargs):
    try:
        if client.can_paginate(method_name):
            return paginated_query_with_retries(client, method_name, **kwargs).get(result_key, [])

        method = getattr(client, method_name)
        available_parameters = get_boto3_client_method_parameters(client, method_name)
        output_members = get_client_method_output_members(client, method_name)
        # Operations such as Route53 ListReusableDelegationSets echo the request
        # Marker and return the next page in NextMarker.
        response_marker_names = ["NextMarker", "NextToken", "nextMarker", "nextToken"]
        if "NextMarker" not in output_members and "nextMarker" not in output_members:
            response_marker_names.extend(["Marker", "marker"])

        marker_name = next(
            (
                name
                for name in (
                    "Marker",
                    "NextMarker",
                    "NextToken",
                    "marker",
                    "nextMarker",
                    "nextToken",
                )
                if name in available_parameters
            ),
            None,
        )
        items = []
        markers = set()
        while True:
            response = method(**kwargs, aws_retry=True)
            items.extend(response.get(result_key, []))
            if response.get("IsTruncated") is False or response.get("isTruncated") is False:
                return items

            marker = next((response[name] for name in response_marker_names if response.get(name)), None)
            if not marker:
                if response.get("IsTruncated") or response.get("isTruncated"):
                    module.fail_json(msg=f"{error_msg}: truncated response without a marker")

                return items

            if marker in markers:
                module.fail_json(msg=f"{error_msg}: repeated pagination marker")

            if marker_name is None:
                module.fail_json(msg=f"{error_msg}: pagination marker has no request parameter")

            markers.add(marker)
            kwargs[marker_name] = marker
    except (BotoCoreError, ClientError) as e:
        module.fail_json_aws(e, msg=error_msg)


def require_client_methods(module, client, service, methods):
    for method_name in methods:
        try:
            available_parameters = get_boto3_client_method_parameters(client, method_name)
        except (AttributeError, OperationNotFoundError):
            module.fail_json(msg=f"Installed botocore does not support {service} {method_name}")

        for parameter_name in sorted(methods[method_name]):
            if parameter_name in available_parameters:
                continue

            module.fail_json(
                msg=f"Installed botocore does not support {service} {method_name} parameter {parameter_name}"
            )
