# Ansible SDK Module Utilities

AWS SDK-specific reference for reusable Ansible `module_utils`. Apply these
with `ansible-module-utils.md`. Confirm version-dependent imports against the
collections installed from `requirements.yml`.

```python
from ansible_collections.amazon.aws.plugins.module_utils.{{ module }} import {{ name }}
from ansible_collections.community.aws.plugins.module_utils.{{ module }} import {{ name }}
```

## amazon.aws

| Module            | Symbol                                  | Use                                      |
| ----------------- | --------------------------------------- | ---------------------------------------- |
| `.arn`            | `parse_aws_arn`                         | Split an ARN into parts.                 |
| `.arn`            | `validate_aws_arn`                      | Validate an ARN's shape.                 |
| `.botocore`       | `boto3_at_least`                        | boto3 version gate.                      |
| `.botocore`       | `boto3_conn`                            | Raw client (prefer `module.client`).     |
| `.botocore`       | `boto_exception`                        | Exception → string.                      |
| `.botocore`       | `botocore_at_least`                     | botocore version gate.                   |
| `.botocore`       | `check_sdk_version_supported`           | Assert SDK version.                      |
| `.botocore`       | `enable_placebo`                        | Test-recording hook (not prod).          |
| `.botocore`       | `gather_sdk_versions`                   | Report SDK versions.                     |
| `.botocore`       | `get_aws_connection_info`               | Raw connection info.                     |
| `.botocore`       | `get_aws_region`                        | Resolve the region.                      |
| `.botocore`       | `get_boto3_client_method_parameters`    | Gate newer SDK APIs.                     |
| `.botocore`       | `is_boto3_error_code`                   | Match a `ClientError` code.              |
| `.botocore`       | `is_boto3_error_httpstatus`             | Match a `ClientError` status.            |
| `.botocore`       | `is_boto3_error_message`                | Match a `ClientError` message.           |
| `.botocore`       | `normalize_boto3_result`                | Normalize a raw response.                |
| `.botocore`       | `paginated_query_with_retries`          | Paginated list/describe; no `aws_retry`. |
| `.common`         | `get_collection_info`                   | Read collection metadata.                |
| `.common`         | `set_collection_info`                   | Set collection metadata.                 |
| `.exceptions`     | `is_ansible_aws_error_code`             | Match `AnsibleAWSError` code.            |
| `.exceptions`     | `is_ansible_aws_error_message`          | Match `AnsibleAWSError` message.         |
| `.iterators`      | `chunked_payload`                       | Split a payload by size.                 |
| `.iterators`      | `chunks`                                | Split a sequence into batches.           |
| `.modules`        | `AnsibleAWSModule`                      | Base class for every module.             |
| `.modules`        | `aws_argument_spec`                     | Base arg spec (prefer fragments).        |
| `.retries`        | `AWSRetry`                              | Retry decorator (jittered backoff).      |
| `.tagging`        | `ansible_dict_to_boto3_tag_list`        | Tag dict → boto3 list.                   |
| `.tagging`        | `ansible_dict_to_tag_filter_dict`       | Build a tag filter.                      |
| `.tagging`        | `boto3_tag_list_to_ansible_dict`        | boto3 list → tag dict.                   |
| `.tagging`        | `boto3_tag_specifications`              | Create-time tag specs.                   |
| `.tagging`        | `compare_aws_tags`                      | Diff desired vs current tags.            |
| `.transformation` | `ansible_dict_to_boto3_filter_list`     | Build boto3 `Filters`.                   |
| `.transformation` | `boto3_resource_list_to_ansible_dict`   | Resource list → snake_case.              |
| `.transformation` | `boto3_resource_to_ansible_dict`        | Resource → snake_case.                   |
| `.transformation` | `map_complex_type`                      | Coerce nested values by type.            |
| `.transformation` | `sanitize_filters_to_boto3_filter_list` | Sanitize + build `Filters`.              |
| `.transformation` | `scrub_none_parameters`                 | Drop unset keys before a call.           |
| `.waiter`         | `custom_waiter_config`                  | Waiter delay/retries config.             |
| `.waiters`        | `get_waiter`                            | Get a waiter.                            |
| `.waiters`        | `wait_for_resource_state`               | Wait on resource state.                  |

## community.aws

| Module     | Symbol                      | Use                                      |
| ---------- | --------------------------- | ---------------------------------------- |
| `.base`    | `BaseResourceManager`       | Class-based manager (we use `ensure_*`). |
| `.base`    | `BaseWaiterFactory`         | Class-based waiter factory.              |
| `.base`    | `Boto3Mixin`                | Class-based boto3 mixin.                 |
| `.modules` | `AnsibleCommunityAWSModule` | Only for community.aws modules.          |
