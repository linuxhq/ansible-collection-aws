# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    get_boto3_client_method_parameters,
    paginated_query_with_retries,
)


def query_list(module, client, method_name, result_key, error_msg, **kwargs):
    try:
        return paginated_query_with_retries(client, method_name, **kwargs).get(
            result_key, []
        )
    except Exception as e:
        module.fail_json_aws(e, msg=error_msg)


def require_client_methods(module, client, service, methods):
    for method_name in methods:
        try:
            available_parameters = get_boto3_client_method_parameters(
                client, method_name
            )
        except Exception:
            module.fail_json(
                msg=f"Installed botocore does not support {service} {method_name}"
            )

        for parameter_name in sorted(methods[method_name]):
            if parameter_name in available_parameters:
                continue

            module.fail_json(
                msg=(
                    f"Installed botocore does not support {service} "
                    f"{method_name} parameter {parameter_name}"
                )
            )
