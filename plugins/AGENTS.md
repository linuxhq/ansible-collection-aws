# AGENTS.md

## Model

gpt-5.5 high

## Workflow

* Read this entire file before making changes
* Apply every section relevant to the requested change
* Use existing collection patterns and helpers before introducing new implementations
* Complete the requested implementation before stopping
* Run the required validation steps after plugin changes
* Do not commit changes to git

## Validation

After plugin changes, run:

* **ansible-test**
  * Use the collection path `venv/ansible_collections/linuxhq/aws`
  * Use a real git worktree or real directory; symlinks are not sufficient
    because `ansible-test` resolves the physical path
  * If the worktree does not exist, create it:
    ```
    mkdir -p venv/ansible_collections/linuxhq
    git worktree add --detach venv/ansible_collections/linuxhq/aws HEAD
    ```
  * Overlay uncommitted changes from the root checkout before running:
    ```
    rsync -a --delete --exclude='.git' --exclude='venv' ./ venv/ansible_collections/linuxhq/aws/
    ```
  * Run from the worktree, using the Python version from the active venv if
    local shim discovery fails:
    ```
    ../../../bin/ansible-test sanity --color no --python 3.12
    ```
* **black**: `venv/bin/black --check plugins`
* **git**: `git diff --check`
* **python**: `venv/bin/python -m compileall -q plugins`

## Standards

### Module behavior

* Keep present and absent flows explicit and easy to follow

* Ensure modules remain idempotent and avoid unnecessary api calls

* Support check mode: never make mutating api calls in check mode; set
  `supports_check_mode=True` and return `changed=False` in info modules;
  return the predicted result shape when practical

* Tag management: use the collection tagging helpers, compare desired and
  current tags before api calls, and only apply `purge_tags` when `tags`
  is provided

* Long-running operations: expose wait controls consistent with nearby modules
  and use existing waiter helpers over custom polling loops

### Arguments

* Accept module parameters in snake_case and transform to boto3 formats using
  existing helpers

* Use `AnsibleAWSModule` validation arguments such as `required_by`,
  `required_if`, `required_one_of`, `required_together`, and `mutually_exclusive`
  over manual parameter validation when they express the rule clearly

* Mark secret parameters with `no_log=True` and exclude their values from
  examples, return values, and error messages

* When writing info modules, expose singular lookup parameters (`name`, `id`,
  `arn`) only when the underlying api accepts a singular identifier. Do not
  substitute plural list parameters (`names`, `ids`, `arns`) for the api's
  native parameter shape

### Documentation

* Keep `DOCUMENTATION`, `EXAMPLES`, `RETURN`, and `argument_spec` aligned when
  adding or changing module parameters, return fields, aliases, choices, or
  defaults

* Include the relevant amazon.aws documentation fragments for
  common options, region handling, and boto3 requirements

* For list options and list return values, include `elements` in
  `DOCUMENTATION` and `RETURN`

* Use the collection fqcn in `EXAMPLES`, such as `linuxhq.aws.<plugin_name>`

* When an option is conditionally required through `required_if`, document
  the condition in the description instead of marking the option `required: true`

### Operations

* Create clients with `AnsibleAWSModule.client` unless an existing pattern
  in the module requires a different helper

* Create clients with `module.client("service", retry_decorator=AWSRetry.jittered_backoff())`
  and pass `aws_retry=True` on individual boto3 api calls that should be retried;
  `paginated_query_with_retries` handles retries internally and does not take `aws_retry`

* When apis or request parameters may be missing from older boto3 or botocore
  versions, validate sdk support in `main()` with `get_boto3_client_method_parameters()`
  before dispatching to state handlers; keep the result local to `main()` and do not
  pass it into `ensure_*` helpers. Fail with `module.fail_json()` naming the
  unsupported service method or parameter.

* Scrub unset optional parameters before passing request dictionaries to boto3
  operations

* Use `paginated_query_with_retries` for paginated list and describe operations
  instead of hand-rolled paginator loops; when an api has no boto3 paginator,
  use a hand-rolled marker/token loop instead

* Wrap api failures with `module.fail_json_aws`, including the resource name
  or identifier in the message when one is available

### Result data

* Return ansible-facing data in snake_case; normalize boto3 responses with the
  existing transformation helpers before including them in `exit_json`

### Implementation style

* Cache a `module.params[...]` value in a local variable only when it is
  accessed two or more times, requires normalization, or its name meaningfully
  clarifies request construction; use `module.params[...]` directly otherwise

* Pass only `module` to helpers that need `module.params` values; read them
  inside the helper rather than extracting and passing them at the call site,
  and do not add `name=None`-style fallback parameters for values owned by
  `module.params`

* If a helper also needs returned values, pass those as required explicit
  arguments rather than mixing explicit and `module.params` fallback parameters

* Never mutate `module.params` after module initialization

* Dispatch on `state` with an explicit `if`/`elif`/`else` chain; always close
  with `module.fail_json(msg=f"Unsupported state: {state}")` in the final
  branch, even when `choices` validation makes it unreachable

* Use explicit loops over nested comprehensions when the loop performs
  api calls or filters missing resources

* Inline a helper into its one call site when it is called from exactly one
  place and is not passed as a callback reference; if the helper catches a
  specific exception and returns `None` with the caller checking for `None`,
  replace that pattern with `continue` when inlining

* Separate logical phases with a single blank line at every level of nesting.
  Apply a blank line before each of the following transitions, unless the
  statement is the very first line in its enclosing block:
  * Before every `try:` statement
  * After the last `except` clause before the next statement at the same level
  * After a guard `continue` or `break` before the next statement in the loop
  * Between any result assignment and subsequent processing of that result

* Do not extract shared module_utils helpers unless several modules genuinely
  need the same stable behavior and the abstraction clearly reduces complexity

### Lookup plugins

* Validate unsupported positional terms and required keyword arguments
  explicitly, and raise `AnsibleLookupError` with actionable messages

## Helper reference

Use existing helpers before implementing custom logic.

* `amazon.aws` module_utils:
  * **arn**:
    * parse_aws_arn
    * validate_aws_arn
  * **botocore**:
    * boto3_at_least
    * boto3_conn
    * boto_exception
    * botocore_at_least
    * check_sdk_version_supported
    * enable_placebo
    * gather_sdk_versions
    * get_aws_connection_info
    * get_aws_region
    * get_boto3_client_method_parameters
    * is_boto3_error_code
    * is_boto3_error_httpstatus
    * is_boto3_error_message
    * normalize_boto3_result
    * paginated_query_with_retries
  * **common**:
    * get_collection_info
    * set_collection_info
  * **exceptions**:
    * is_ansible_aws_error_code
    * is_ansible_aws_error_message
  * **iterators**:
    * chunked_payload
    * chunks
  * **modules**:
    * AnsibleAWSModule
    * aws_argument_spec
  * **retries**:
    * AWSRetry
  * **tagging**:
    * ansible_dict_to_boto3_tag_list
    * ansible_dict_to_tag_filter_dict
    * boto3_tag_list_to_ansible_dict
    * boto3_tag_specifications
    * compare_aws_tags
  * **transformation**:
    * ansible_dict_to_boto3_filter_list
    * boto3_resource_list_to_ansible_dict
    * boto3_resource_to_ansible_dict
    * map_complex_type
    * sanitize_filters_to_boto3_filter_list
    * scrub_none_parameters
  * **waiter**:
    * custom_waiter_config
  * **waiters**:
    * get_waiter
    * wait_for_resource_state

* `ansible.module_utils`:
  * **basic**:
    * get_all_subclasses
    * get_module_path
    * get_platform
    * heuristic_log_sanitize
    * load_platform_subclass
    * missing_required_lib
  * **common.collections**:
    * count
    * is_iterable
    * is_sequence
    * is_string
  * **common.dict_transformations**:
    * camel_dict_to_snake_dict
    * dict_merge
    * recursive_diff
    * snake_dict_to_camel_dict
  * **common.json**:
    * get_decoder
    * get_encoder
    * get_module_decoder
    * get_module_encoder
  * **common.parameters**:
    * env_fallback
    * remove_values
    * sanitize_keys
    * set_fallbacks
  * **common.text.converters**:
    * container_to_bytes
    * container_to_text
    * jsonify
    * to_bytes
    * to_text
  * **common.text.formatters**:
    * bytes_to_human
    * human_to_bytes
    * lenient_lowercase
  * **common.validation**:
    * check_missing_parameters
    * check_mutually_exclusive
    * check_required_arguments
    * check_required_by
    * check_required_if
    * check_required_one_of
    * check_required_together
    * check_type_bits
    * check_type_bool
    * check_type_bytes
    * check_type_dict
    * check_type_float
    * check_type_int
    * check_type_jsonarg
    * check_type_list
    * check_type_path
    * check_type_raw
    * check_type_str
    * count_terms
