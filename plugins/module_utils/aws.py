#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry


def _aws_error_message(operation):
    return f"Unable to call AWS operation {operation}"


def _aws_operation(client, operation):
    return AWSRetry.jittered_backoff()(getattr(client, operation))


def _fail_aws_operation(module, operation, error, error_message=None):
    module.fail_json_aws(error, msg=error_message or _aws_error_message(operation))


def _response_result(response, result_key, default):
    return response.get(result_key, default)


def _paginated_list_default(default):
    return default if default is not None else []


def _marker_request_kwargs(initial_kwargs, marker_arg, marker):
    kwargs = dict(initial_kwargs or {})
    if marker:
        kwargs[marker_arg] = marker
    return kwargs


def _marker_page_finished(response, marker, truncated_result):
    if truncated_result and not response.get(truncated_result):
        return True
    return not marker


def aws_response(
    client,
    module,
    operation,
    error_message=None,
    ignore_error_codes=None,
    ignored_error_result=None,
    **kwargs,
):
    try:
        return _aws_operation(client, operation)(**kwargs)
    except is_boto3_error_code(ignore_error_codes):
        return ignored_error_result
    except Exception as e:
        _fail_aws_operation(module, operation, e, error_message)


def aws_resource(
    client,
    module,
    operation,
    result_key,
    error_message=None,
    default=None,
    ignore_error_codes=None,
    ignored_error_result=None,
    **kwargs,
):
    response = aws_response(
        client,
        module,
        operation,
        error_message,
        ignore_error_codes=ignore_error_codes,
        ignored_error_result=ignored_error_result,
        **kwargs,
    )
    if response is ignored_error_result:
        return ignored_error_result
    return _response_result(response, result_key, default)


def _aws_paginated_response(
    client,
    module,
    operation,
    error_message=None,
    ignore_error_codes=None,
    ignored_error_result=None,
    **kwargs,
):
    try:
        return paginated_query_with_retries(client, operation, **kwargs)
    except is_boto3_error_code(ignore_error_codes):
        return ignored_error_result
    except Exception as e:
        _fail_aws_operation(module, operation, e, error_message)


def aws_paginated_list(
    client,
    module,
    operation,
    result_key,
    error_message=None,
    default=None,
    ignore_error_codes=None,
    ignored_error_result=None,
    **kwargs,
):
    response = _aws_paginated_response(
        client,
        module,
        operation,
        error_message,
        ignore_error_codes=ignore_error_codes,
        ignored_error_result=ignored_error_result,
        **kwargs,
    )
    if response is ignored_error_result:
        return ignored_error_result
    return _response_result(response, result_key, _paginated_list_default(default))


def aws_marker_paginated_list(
    client,
    module,
    operation,
    result_key,
    error_message=None,
    marker_arg="Marker",
    next_marker_arg=None,
    next_marker_result="NextMarker",
    truncated_result=None,
    initial_kwargs=None,
):
    operation_call = _aws_operation(client, operation)
    items = []
    marker = None
    try:
        while True:
            response = operation_call(
                **_marker_request_kwargs(initial_kwargs, marker_arg, marker)
            )
            items.extend(response.get(result_key, []))

            marker = response.get(next_marker_result)
            if _marker_page_finished(response, marker, truncated_result):
                break

            marker_arg = next_marker_arg or marker_arg
    except Exception as e:
        _fail_aws_operation(module, operation, e, error_message)

    return items
