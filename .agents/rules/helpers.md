# Helper reference

Prefer these existing helpers over hand-written logic. Before implementing tag
comparison, ARN parsing, pagination, filtering, dict case-conversion, waiters, or
parameter validation, check for a helper here first — reimplementing one is a review
and sanity-test failure.

These are the core `module_utils` helpers provided by the `amazon.aws` and `community.aws`
collections (declared in `galaxy.yml`) and by `ansible-core`. They are stable public
building blocks. Symbols are grouped under the exact module to import them from, so each
line below is directly usable.

Import form:

```python
from ansible_collections.amazon.aws.plugins.module_utils.<module> import <name>
from ansible_collections.community.aws.plugins.module_utils.<module> import <name>
from ansible.module_utils.<module> import <name>
```

Prefer `amazon.aws` helpers for anything generic (tags, filters, pagination, ARNs,
waiters). Reach into `community.aws` only for the service it targets — most of its helpers
are service-scoped (SNS, WAFv2, DynamoDB, OpenSearch, Network Firewall).

## amazon.aws — `ansible_collections.amazon.aws.plugins.module_utils`

### `.arn`
- `parse_aws_arn` — split an ARN into its components; use before string-slicing an ARN.
- `validate_aws_arn` — validate ARN shape and optionally its partition/service/region.

### `.botocore`
- `boto3_at_least`, `botocore_at_least` — SDK version gates.
- `boto3_conn`, `get_aws_connection_info`, `get_aws_region` — low-level connection setup
  (prefer `AnsibleAWSModule.client`; use these only when a module needs raw connection info).
- `boto_exception` — render a boto exception to a message string.
- `check_sdk_version_supported`, `gather_sdk_versions` — assert/report installed SDK versions.
- `get_boto3_client_method_parameters` — inspect a client method's accepted parameters;
  use in `main()` to fail early when older boto3/botocore lacks an API or request field.
- `is_boto3_error_code`, `is_boto3_error_httpstatus`, `is_boto3_error_message` — match a
  specific `ClientError` in `except` clauses instead of inspecting the exception by hand.
- `normalize_boto3_result` — normalize a raw boto3 response (e.g. datetimes) for return.
- `paginated_query_with_retries` — run a paginated list/describe with built-in retries.
  Do not pass `aws_retry=True` to it; it handles retries internally. Use this instead of
  hand-rolled paginator loops (fall back to a manual marker/token loop only when the API
  has no boto3 paginator).
- `enable_placebo` — test-recording hook; not for production module code.

### `.exceptions`
- `is_ansible_aws_error_code`, `is_ansible_aws_error_message` — match errors raised as
  `AnsibleAWSError` (the collection's wrapped form).

### `.modules`
- `AnsibleAWSModule` — the base module class; construct every module with it.
- `aws_argument_spec` — shared base argument spec (prefer the documentation fragments in
  `DOCUMENTATION`; use this only if a module builds its spec programmatically).

### `.retries`
- `AWSRetry` — retry decorator. Standard client creation:
  `module.client("<svc>", retry_decorator=AWSRetry.jittered_backoff())`, then pass
  `aws_retry=True` on the individual calls that should retry.

### `.tagging`
- `compare_aws_tags` — diff desired vs current tags into (to-set, to-remove) before any
  tag API call; only honor `purge_tags` when `tags` was provided.
- `ansible_dict_to_boto3_tag_list`, `boto3_tag_list_to_ansible_dict` — convert between the
  Ansible tag dict and the boto3 `[{Key,Value}]` list.
- `ansible_dict_to_tag_filter_dict`, `boto3_tag_specifications` — build tag filters and
  create-time `TagSpecifications`.

### `.transformation`
- `scrub_none_parameters` — drop unset (`None`) keys from a request dict before calling
  boto3; use before every mutating call that builds params conditionally.
- `ansible_dict_to_boto3_filter_list`, `sanitize_filters_to_boto3_filter_list` — build
  boto3 `Filters` from Ansible-style filter input.
- `boto3_resource_to_ansible_dict`, `boto3_resource_list_to_ansible_dict` — normalize a
  resource (or list) to snake_case Ansible output.
- `map_complex_type` — coerce nested values by a type map when reshaping input/output.

### `.waiters`
- `get_waiter`, `wait_for_resource_state` — wait on resource state; prefer over custom
  polling loops.

### `.waiter`
- `custom_waiter_config` — build a waiter config (delay/retries) consistent with the
  module's wait options.

### `.common`
- `get_collection_info`, `set_collection_info` — collection metadata access; rarely needed
  in resource modules.

## community.aws — `ansible_collections.community.aws.plugins.module_utils`

Only the collection-wide base/core building blocks are listed here. `community.aws` also
ships service-specific helpers (SNS, WAFv2, DynamoDB, OpenSearch, Network Firewall, S3
ETag); those are out of scope for this reference — read the relevant `community.aws`
`module_utils` module directly if you genuinely need one.

### `.modules`
- `AnsibleCommunityAWSModule` — `AnsibleAWSModule` subclass; only for modules that live in
  `community.aws` itself. New modules in this collection use `amazon.aws`'s `AnsibleAWSModule`.

### `.base`
- `BaseResourceManager`, `Boto3Mixin`, `BaseWaiterFactory` — the class-based
  resource-manager pattern. Adopt only when extending a module already built on it; the
  modules here use the simpler `ensure_*` function style.

## ansible-core — `ansible.module_utils`

### `.common.dict_transformations`
- `camel_dict_to_snake_dict`, `snake_dict_to_camel_dict` — convert case between boto3 and
  Ansible-facing data.
- `dict_merge` — deep-merge dicts.
- `recursive_diff` — structural diff of two dicts (idempotency/change detection).

### `.common.validation`
- `check_required_by`, `check_required_if`, `check_required_one_of`, `check_required_together`,
  `check_mutually_exclusive`, `check_required_arguments`, `check_missing_parameters`,
  `count_terms` — parameter-relationship checks. Prefer declaring these as `AnsibleAWSModule`
  arguments (`required_by`, `required_if`, `mutually_exclusive`, …); call these functions
  directly only for conditional logic the spec cannot express.
- `check_type_bool`, `check_type_int`, `check_type_float`, `check_type_str`, `check_type_list`,
  `check_type_dict`, `check_type_path`, `check_type_bytes`, `check_type_bits`,
  `check_type_jsonarg`, `check_type_raw` — coerce/validate a single value's type.

### `.common.text.converters`
- `to_bytes`, `to_text` — encoding-safe string conversion.
- `container_to_bytes`, `container_to_text`, `jsonify` — recursive conversion / JSON encode.

### `.common.text.formatters`
- `bytes_to_human`, `human_to_bytes` — size string ↔ integer bytes.
- `lenient_lowercase` — lowercase items, skipping non-strings.

### `.common.collections`
- `is_iterable`, `is_sequence`, `is_string`, `count` — type/shape predicates for input
  normalization.

### `.common.parameters`
- `env_fallback` — argument-spec default sourced from an environment variable.
- `remove_values`, `sanitize_keys` — strip `no_log` values from output/errors.
- `set_fallbacks` — apply fallback callables to params.

### `.common.json`
- `get_decoder`, `get_encoder`, `get_module_decoder`, `get_module_encoder` — JSON
  encoders/decoders that understand Ansible/module types.

### `.basic`
- `missing_required_lib` — build the standard "install X" message when an optional import
  is absent.
- `heuristic_log_sanitize` — scrub secrets from a string before logging.
- `get_all_subclasses`, `get_module_path`, `get_platform`, `load_platform_subclass` —
  low-level platform/introspection helpers; rarely needed in AWS modules.
