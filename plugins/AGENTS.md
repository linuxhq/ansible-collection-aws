# AGENTS.md

## Model

gpt-5.5 high

## Standards

* Support check mode

* Keep present and absent flows explicit and easy to follow

* Ensure modules remain idempotent and avoid unnecessary aws api calls

* Keep implementations consistent with existing amazon.aws module patterns

* Accept module parameters in snake_case and transform to boto3 formats
  using existing helpers

* Prefer the following collection helpers before implementing custom logic
  * ansible.module_utils
  * ansible_collections.amazon.aws.plugins.module_utils

* Use existing amazon.aws helpers listed below, including but not limited to
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
  * ansible_collections.amazon.aws.plugins.module_utils.modules.aws_argument_spec
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

* Use existing ansible helpers listed below, including but not limited to
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

* Complete the requested implementation before stopping

* Do not commit changes
