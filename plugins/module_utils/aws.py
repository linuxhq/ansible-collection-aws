#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.common.dict_transformations import snake_dict_to_camel_dict
from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    scrub_none_parameters,
)


def _aws_marker_paginated_resources(
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
    base_request = dict(initial_kwargs or {})
    marker = None
    try:
        while True:
            request = dict(base_request)
            if marker:
                request[marker_arg] = marker

            response = operation_call(**request)
            for resource in response.get(result_key, []):
                yield resource

            marker = response.get(next_marker_result)
            if (truncated_result and not response.get(truncated_result)) or not marker:
                break

            marker_arg = next_marker_arg or marker_arg
    except Exception as e:
        _fail_aws_operation(module, operation, e, error_message)


def _aws_operation(client, operation):
    return AWSRetry.jittered_backoff()(getattr(client, operation))


def _fail_aws_operation(module, operation, error, error_message=None):
    module.fail_json_aws(
        error,
        msg=error_message or f"Unable to call AWS operation {operation}",
    )


def aws_marker_paginated_find(
    client,
    module,
    operation,
    result_key,
    matcher,
    error_message=None,
    marker_arg="Marker",
    next_marker_arg=None,
    next_marker_result="NextMarker",
    truncated_result=None,
    initial_kwargs=None,
):
    for resource in _aws_marker_paginated_resources(
        client,
        module,
        operation,
        result_key,
        error_message,
        marker_arg,
        next_marker_arg,
        next_marker_result,
        truncated_result,
        initial_kwargs,
    ):
        if matcher(resource):
            return resource
    return None


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
    return list(
        _aws_marker_paginated_resources(
            client,
            module,
            operation,
            result_key,
            error_message,
            marker_arg,
            next_marker_arg,
            next_marker_result,
            truncated_result,
            initial_kwargs,
        )
    )


def aws_paginated_find(
    client,
    module,
    operation,
    result_key,
    matcher,
    error_message=None,
    ignore_error_codes=None,
    ignored_error_result=None,
    **kwargs,
):
    def paginated_find(client, operation, result_key, matcher, **kwargs):
        paginator = client.get_paginator(operation)
        for page in paginator.paginate(**kwargs):
            for resource in page.get(result_key, []):
                if matcher(resource):
                    return resource
        return None

    try:
        return AWSRetry.jittered_backoff(retries=10)(paginated_find)(
            client,
            operation,
            result_key,
            matcher,
            **kwargs,
        )
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
    try:
        response = paginated_query_with_retries(client, operation, **kwargs)
    except is_boto3_error_code(ignore_error_codes):
        return ignored_error_result
    except Exception as e:
        _fail_aws_operation(module, operation, e, error_message)

    return response.get(result_key, default if default is not None else [])


def aws_request_params(params, capitalize_first=True):
    return scrub_none_parameters(
        snake_dict_to_camel_dict(params, capitalize_first=capitalize_first)
    )


def aws_request_params_list(items, capitalize_first=True):
    return [
        aws_request_params(item, capitalize_first=capitalize_first) for item in items
    ]


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
    return response.get(result_key, default)


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
