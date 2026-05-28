# AGENTS.md

## Model

gpt-5.5 high

## Standards

### Module behavior

* Keep present and absent flows explicit and easy to follow

* Ensure modules remain idempotent and avoid unnecessary aws api calls

* Support check mode
  * Do not make mutating aws api calls in check mode
  * Info modules
    * Set `supports_check_mode=True`
    * Return `changed=False`
  * Return the predicted result shape when practical

* Tag management
  * Use the collection tagging helpers
  * Compare desired and current tags before calling aws
  * Only apply `purge_tags` when `tags` is provided

* Long-running operations
  * Expose wait controls consistent with nearby modules
  * Prefer existing waiter helpers over custom polling loops

### Arguments

* Accept module parameters in snake_case and transform to boto3 formats using
  existing helpers

* Prefer `AnsibleAWSModule` validation arguments such as `required_if`,
  `required_one_of`, `required_together`, and `mutually_exclusive` over manual
  parameter validation when they express the rule clearly

* Secret module parameters
  * Mark parameters with `no_log=True`
  * Do not include secret values in examples, return values, or error messages

### Documentation

* Keep `DOCUMENTATION`, `EXAMPLES`, `RETURN`, and `argument_spec` aligned when
  adding or changing module parameters, return fields, aliases, choices, or
  defaults

* For aws modules, include the relevant amazon.aws documentation fragments for
  common options, region handling, and boto3 requirements

* For list options and list return values, include `elements` in
  `DOCUMENTATION` and `RETURN`

* Use the collection fqcn in `EXAMPLES`, such as `linuxhq.aws.<plugin_name>`

* When an option is conditionally required through `required_if`, document
  the condition in the description instead of marking the option `required: true`

### Operations

* Create aws clients with `AnsibleAWSModule.client` unless an existing pattern
  in the module requires a different helper

* Use `AWSRetry.jittered_backoff()` for aws api calls that need retries

* When using aws apis that may be missing from older boto3 or botocore versions,
  use the collection sdk/version helpers and fail with a clear module error

* Scrub unset optional parameters before passing request dictionaries to boto3
  operations

* Use `paginated_query_with_retries` for paginated list and describe operations
  instead of hand-rolled paginator loops

* Wrap aws api failures with `module.fail_json_aws`, including the resource name
  or identifier in the message when one is available

### Result data

* Return ansible-facing data in snake_case; normalize boto3 responses with the
  existing transformation helpers before including them in `exit_json`

### Implementation style

* Keep changes focused on measurable behavior, consistency, or documentation
  correctness; avoid broad style churn

* Keep implementations consistent with existing amazon.aws module patterns
  * Use direct `module.params[...]` access for simple or one-off values
  * Introduce local variables only when the value is reused, normalized,
    or clarifies request construction
  * Do not pass `module` and `module.params[...]` to the same function call;
    when the value is only forwarded from `module.params`, read it inside the
    callee
  * Do not add optional fallback parameters such as `name=None` for values that
    are owned by `module.params`; make the callee read `module.params[...]`
    directly
  * If a helper must also handle non-parameter values returned by aws, keep that
    value as a required explicit argument or use a separate helper instead of
    mixing explicit arguments with `module.params` fallbacks
  * Never mutate `module.params` after module initialization

* Prefer explicit loops over nested comprehensions when the loop performs
  aws api calls or filters missing aws resources

* Do not extract shared module_utils helpers unless several modules genuinely
  need the same stable behavior and the abstraction clearly reduces complexity

### Lookup plugins

* Validate unsupported positional terms and required keyword arguments
  explicitly, and raise `AnsibleLookupError` with actionable messages

## Helper reference

* Prefer existing ansible and amazon.aws helpers before implementing custom
  logic

* Use existing amazon.aws helpers, including
  * ansible_collections.amazon.aws.plugins.module_utils.arn.parse_aws_arn
  * ansible_collections.amazon.aws.plugins.module_utils.arn.validate_aws_arn
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.boto3_at_least
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.boto3_conn
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.boto_exception
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.botocore_at_least
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.check_sdk_version_supported
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.enable_placebo
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.gather_sdk_versions
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.get_aws_connection_info
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.get_aws_region
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.get_boto3_client_method_parameters
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.is_boto3_error_code
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.is_boto3_error_httpstatus
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.is_boto3_error_message
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.normalize_boto3_result
  * ansible_collections.amazon.aws.plugins.module_utils.botocore.paginated_query_with_retries
  * ansible_collections.amazon.aws.plugins.module_utils.common.get_collection_info
  * ansible_collections.amazon.aws.plugins.module_utils.common.set_collection_info
  * ansible_collections.amazon.aws.plugins.module_utils.exceptions.is_ansible_aws_error_code
  * ansible_collections.amazon.aws.plugins.module_utils.exceptions.is_ansible_aws_error_message
  * ansible_collections.amazon.aws.plugins.module_utils.iterators.chunked_payload
  * ansible_collections.amazon.aws.plugins.module_utils.iterators.chunks
  * ansible_collections.amazon.aws.plugins.module_utils.modules.AnsibleAWSModule
  * ansible_collections.amazon.aws.plugins.module_utils.modules.aws_argument_spec
  * ansible_collections.amazon.aws.plugins.module_utils.retries.AWSRetry
  * ansible_collections.amazon.aws.plugins.module_utils.tagging.ansible_dict_to_boto3_tag_list
  * ansible_collections.amazon.aws.plugins.module_utils.tagging.ansible_dict_to_tag_filter_dict
  * ansible_collections.amazon.aws.plugins.module_utils.tagging.boto3_tag_list_to_ansible_dict
  * ansible_collections.amazon.aws.plugins.module_utils.tagging.boto3_tag_specifications
  * ansible_collections.amazon.aws.plugins.module_utils.tagging.compare_aws_tags
  * ansible_collections.amazon.aws.plugins.module_utils.transformation.ansible_dict_to_boto3_filter_list
  * ansible_collections.amazon.aws.plugins.module_utils.transformation.boto3_resource_list_to_ansible_dict
  * ansible_collections.amazon.aws.plugins.module_utils.transformation.boto3_resource_to_ansible_dict
  * ansible_collections.amazon.aws.plugins.module_utils.transformation.map_complex_type
  * ansible_collections.amazon.aws.plugins.module_utils.transformation.sanitize_filters_to_boto3_filter_list
  * ansible_collections.amazon.aws.plugins.module_utils.transformation.scrub_none_parameters
  * ansible_collections.amazon.aws.plugins.module_utils.waiter.custom_waiter_config
  * ansible_collections.amazon.aws.plugins.module_utils.waiters.get_waiter
  * ansible_collections.amazon.aws.plugins.module_utils.waiters.wait_for_resource_state

* Use existing ansible helpers, including
  * ansible.module_utils.basic.get_all_subclasses
  * ansible.module_utils.basic.get_module_path
  * ansible.module_utils.basic.get_platform
  * ansible.module_utils.basic.heuristic_log_sanitize
  * ansible.module_utils.basic.load_platform_subclass
  * ansible.module_utils.basic.missing_required_lib
  * ansible.module_utils.common.collections.count
  * ansible.module_utils.common.collections.is_iterable
  * ansible.module_utils.common.collections.is_sequence
  * ansible.module_utils.common.collections.is_string
  * ansible.module_utils.common.dict_transformations.camel_dict_to_snake_dict
  * ansible.module_utils.common.dict_transformations.dict_merge
  * ansible.module_utils.common.dict_transformations.recursive_diff
  * ansible.module_utils.common.dict_transformations.snake_dict_to_camel_dict
  * ansible.module_utils.common.json.get_decoder
  * ansible.module_utils.common.json.get_encoder
  * ansible.module_utils.common.json.get_module_decoder
  * ansible.module_utils.common.json.get_module_encoder
  * ansible.module_utils.common.parameters.env_fallback
  * ansible.module_utils.common.parameters.remove_values
  * ansible.module_utils.common.parameters.sanitize_keys
  * ansible.module_utils.common.parameters.set_fallbacks
  * ansible.module_utils.common.text.converters.container_to_bytes
  * ansible.module_utils.common.text.converters.container_to_text
  * ansible.module_utils.common.text.converters.jsonify
  * ansible.module_utils.common.text.converters.to_bytes
  * ansible.module_utils.common.text.converters.to_text
  * ansible.module_utils.common.text.formatters.bytes_to_human
  * ansible.module_utils.common.text.formatters.human_to_bytes
  * ansible.module_utils.common.text.formatters.lenient_lowercase
  * ansible.module_utils.common.validation.check_missing_parameters
  * ansible.module_utils.common.validation.check_mutually_exclusive
  * ansible.module_utils.common.validation.check_required_arguments
  * ansible.module_utils.common.validation.check_required_by
  * ansible.module_utils.common.validation.check_required_if
  * ansible.module_utils.common.validation.check_required_one_of
  * ansible.module_utils.common.validation.check_required_together
  * ansible.module_utils.common.validation.check_type_bits
  * ansible.module_utils.common.validation.check_type_bool
  * ansible.module_utils.common.validation.check_type_bytes
  * ansible.module_utils.common.validation.check_type_dict
  * ansible.module_utils.common.validation.check_type_float
  * ansible.module_utils.common.validation.check_type_int
  * ansible.module_utils.common.validation.check_type_jsonarg
  * ansible.module_utils.common.validation.check_type_list
  * ansible.module_utils.common.validation.check_type_path
  * ansible.module_utils.common.validation.check_type_raw
  * ansible.module_utils.common.validation.check_type_str
  * ansible.module_utils.common.validation.count_terms

## Validation

* After plugin changes, run
  * ansible-test
    * Use the collection path `venv/ansible_collections/linuxhq/aws`
    * Use a real git worktree or real directory for that collection path;
      symlinks are not sufficient because `ansible-test` resolves the physical
      path
    * If the worktree does not exist, create it
      * `mkdir -p venv/ansible_collections/linuxhq`
      * `git worktree add --detach venv/ansible_collections/linuxhq/aws HEAD`
    * To test uncommitted changes from the root checkout, overlay the current
      tree into the worktree
      * `rsync -a --delete --exclude='.git' --exclude='venv' ./ venv/ansible_collections/linuxhq/aws/`
    * If the default Python discovery fails because local shims are unavailable,
      run sanity from the worktree with the Python version from the active venv
      * `../../../bin/ansible-test sanity --color no --python 3.12`
  * black
    * `venv/bin/black --check plugins`
  * git
    * `git diff --check`
  * python
    * `venv/bin/python -m compileall -q plugins`

## Workflow

* Complete the requested implementation before stopping

* Do not commit changes
