# Helpers

Prefer these `module_utils` helpers over hand-rolled logic — reimplementing one fails review and
sanity. They cover:

- tags
- ARNs
- pagination
- filters
- case conversion
- waiters
- validation

Import from the module shown; use `amazon.aws` for generic needs, `community.aws` only for its
service.

```python
from ansible_collections.amazon.aws.plugins.module_utils.<module> import <name>
from ansible_collections.community.aws.plugins.module_utils.<module> import <name>
from ansible.module_utils.<module> import <name>
```

## amazon.aws

| Module            | Symbol                                  | Use                                      |
| ----------------- | --------------------------------------- | ---------------------------------------- |
| `.arn`            | `parse_aws_arn`                         | Split an ARN into parts.                 |
| `.arn`            | `validate_aws_arn`                      | Validate an ARN's shape.                 |
| `.botocore`       | `boto3_at_least`                        | boto3 version gate.                      |
| `.botocore`       | `botocore_at_least`                     | botocore version gate.                   |
| `.botocore`       | `boto3_conn`                            | Raw client (prefer `module.client`).     |
| `.botocore`       | `get_aws_connection_info`               | Raw connection info.                     |
| `.botocore`       | `get_aws_region`                        | Resolve the region.                      |
| `.botocore`       | `boto_exception`                        | Exception → string.                      |
| `.botocore`       | `check_sdk_version_supported`           | Assert SDK version.                      |
| `.botocore`       | `gather_sdk_versions`                   | Report SDK versions.                     |
| `.botocore`       | `get_boto3_client_method_parameters`    | Gate newer SDK APIs.                     |
| `.botocore`       | `is_boto3_error_code`                   | Match a `ClientError` code.              |
| `.botocore`       | `is_boto3_error_httpstatus`             | Match a `ClientError` status.            |
| `.botocore`       | `is_boto3_error_message`                | Match a `ClientError` message.           |
| `.botocore`       | `normalize_boto3_result`                | Normalize a raw response.                |
| `.botocore`       | `paginated_query_with_retries`          | Paginated list/describe; no `aws_retry`. |
| `.botocore`       | `enable_placebo`                        | Test-recording hook (not prod).          |
| `.common`         | `get_collection_info`                   | Read collection metadata.                |
| `.common`         | `set_collection_info`                   | Set collection metadata.                 |
| `.exceptions`     | `is_ansible_aws_error_code`             | Match `AnsibleAWSError` code.            |
| `.exceptions`     | `is_ansible_aws_error_message`          | Match `AnsibleAWSError` message.         |
| `.iterators`      | `chunks`                                | Split a sequence into batches.           |
| `.iterators`      | `chunked_payload`                       | Split a payload by size.                 |
| `.modules`        | `AnsibleAWSModule`                      | Base class for every module.             |
| `.modules`        | `aws_argument_spec`                     | Base arg spec (prefer fragments).        |
| `.retries`        | `AWSRetry`                              | Retry decorator (jittered backoff).      |
| `.tagging`        | `compare_aws_tags`                      | Diff desired vs current tags.            |
| `.tagging`        | `ansible_dict_to_boto3_tag_list`        | Tag dict → boto3 list.                   |
| `.tagging`        | `boto3_tag_list_to_ansible_dict`        | boto3 list → tag dict.                   |
| `.tagging`        | `ansible_dict_to_tag_filter_dict`       | Build a tag filter.                      |
| `.tagging`        | `boto3_tag_specifications`              | Create-time tag specs.                   |
| `.transformation` | `scrub_none_parameters`                 | Drop unset keys before a call.           |
| `.transformation` | `ansible_dict_to_boto3_filter_list`     | Build boto3 `Filters`.                   |
| `.transformation` | `sanitize_filters_to_boto3_filter_list` | Sanitize + build `Filters`.              |
| `.transformation` | `boto3_resource_to_ansible_dict`        | Resource → snake_case.                   |
| `.transformation` | `boto3_resource_list_to_ansible_dict`   | Resource list → snake_case.              |
| `.transformation` | `map_complex_type`                      | Coerce nested values by type.            |
| `.waiter`         | `custom_waiter_config`                  | Waiter delay/retries config.             |
| `.waiters`        | `get_waiter`                            | Get a waiter.                            |
| `.waiters`        | `wait_for_resource_state`               | Wait on resource state.                  |

## community.aws

| Module     | Symbol                      | Use                                      |
| ---------- | --------------------------- | ---------------------------------------- |
| `.base`    | `BaseResourceManager`       | Class-based manager (we use `ensure_*`). |
| `.base`    | `Boto3Mixin`                | Class-based boto3 mixin.                 |
| `.base`    | `BaseWaiterFactory`         | Class-based waiter factory.              |
| `.modules` | `AnsibleCommunityAWSModule` | Only for community.aws modules.          |

## ansible-core

| Module                         | Symbol                     | Use                           |
| ------------------------------ | -------------------------- | ----------------------------- |
| `.basic`                       | `missing_required_lib`     | "install X" message.          |
| `.basic`                       | `heuristic_log_sanitize`   | Scrub secrets before logging. |
| `.basic`                       | `get_all_subclasses`       | All subclasses.               |
| `.basic`                       | `get_module_path`          | Module file path.             |
| `.basic`                       | `get_platform`             | Platform name.                |
| `.basic`                       | `load_platform_subclass`   | Load platform subclass.       |
| `.common.collections`          | `is_iterable`              | Is it iterable?               |
| `.common.collections`          | `is_sequence`              | Is it a sequence?             |
| `.common.collections`          | `is_string`                | Is it a string?               |
| `.common.collections`          | `count`                    | Count occurrences.            |
| `.common.dict_transformations` | `camel_dict_to_snake_dict` | boto3 → snake_case.           |
| `.common.dict_transformations` | `snake_dict_to_camel_dict` | snake_case → boto3.           |
| `.common.dict_transformations` | `dict_merge`               | Deep-merge dicts.             |
| `.common.dict_transformations` | `recursive_diff`           | Structural diff.              |
| `.common.json`                 | `get_decoder`              | JSON decoder.                 |
| `.common.json`                 | `get_encoder`              | JSON encoder.                 |
| `.common.json`                 | `get_module_decoder`       | Module JSON decoder.          |
| `.common.json`                 | `get_module_encoder`       | Module JSON encoder.          |
| `.common.parameters`           | `env_fallback`             | Default from env var.         |
| `.common.parameters`           | `remove_values`            | Strip `no_log` values.        |
| `.common.parameters`           | `sanitize_keys`            | Strip `no_log` keys.          |
| `.common.parameters`           | `set_fallbacks`            | Apply fallback callables.     |
| `.common.text.converters`      | `to_bytes`                 | Safe str → bytes.             |
| `.common.text.converters`      | `to_text`                  | Safe bytes → str.             |
| `.common.text.converters`      | `container_to_bytes`       | Recursively → bytes.          |
| `.common.text.converters`      | `container_to_text`        | Recursively → text.           |
| `.common.text.converters`      | `jsonify`                  | JSON-encode.                  |
| `.common.text.formatters`      | `bytes_to_human`           | Bytes → human size.           |
| `.common.text.formatters`      | `human_to_bytes`           | Human size → bytes.           |
| `.common.text.formatters`      | `lenient_lowercase`        | Lowercase, skip non-str.      |
| `.common.validation`           | `check_required_by`        | Required-by check.            |
| `.common.validation`           | `check_required_if`        | Required-if check.            |
| `.common.validation`           | `check_required_one_of`    | Required-one-of check.        |
| `.common.validation`           | `check_required_together`  | Required-together check.      |
| `.common.validation`           | `check_mutually_exclusive` | Mutually-exclusive check.     |
| `.common.validation`           | `check_required_arguments` | Required-args check.          |
| `.common.validation`           | `check_missing_parameters` | Missing-params check.         |
| `.common.validation`           | `count_terms`              | Count present terms.          |
| `.common.validation`           | `check_type_bool`          | Coerce to bool.               |
| `.common.validation`           | `check_type_int`           | Coerce to int.                |
| `.common.validation`           | `check_type_float`         | Coerce to float.              |
| `.common.validation`           | `check_type_str`           | Coerce to str.                |
| `.common.validation`           | `check_type_list`          | Coerce to list.               |
| `.common.validation`           | `check_type_dict`          | Coerce to dict.               |
| `.common.validation`           | `check_type_path`          | Coerce to path.               |
| `.common.validation`           | `check_type_bytes`         | Coerce to bytes.              |
| `.common.validation`           | `check_type_bits`          | Coerce to bits.               |
| `.common.validation`           | `check_type_jsonarg`       | Coerce to JSON arg.           |
| `.common.validation`           | `check_type_raw`           | Pass through raw.             |
