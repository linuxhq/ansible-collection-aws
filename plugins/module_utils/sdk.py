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


def query_list(module, client, method_name, result_key, error_msg, **kwargs):
    try:
        if client.can_paginate(method_name):
            return paginated_query_with_retries(client, method_name, **kwargs).get(result_key, [])

        method = getattr(client, method_name)
        available_parameters = get_boto3_client_method_parameters(client, method_name)
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
            marker = (
                response.get("NextMarker")
                or response.get("Marker")
                or response.get("NextToken")
                or response.get("nextMarker")
                or response.get("marker")
                or response.get("nextToken")
            )
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
                msg=(f"Installed botocore does not support {service} " f"{method_name} parameter {parameter_name}")
            )
