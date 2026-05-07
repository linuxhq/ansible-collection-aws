# AGENTS.md

## Model

gpt-5.5 xhigh

## Standards

- Support check mode

- Accept module parameters in snake_case and transform to boto3 formats
  using existing helpers where appropriate

- Keep implementations simple, idempotent, and consistent with existing
  amazon.aws module patterns

- Keep present and absent flows explicit and easy to follow

- Do not create custom helpers unless functionality is shared across multiple
  modules in the same AWS service and no existing helper exists

- Prefer existing helpers from ansible.module_utils and
  ansible_collections.amazon.aws.plugins.module_utils before implementing
  custom logic

- Prefer existing helpers listed below, including but not limited to:

    - ansible.module_utils.basic.missing_required_lib
    - ansible.module_utils.common.dict_transformations.camel_dict_to_snake_dict
    - ansible.module_utils.common.dict_transformations.recursive_diff
    - ansible.module_utils.common.dict_transformations.snake_dict_to_camel_dict
    - ansible.module_utils.common.parameters.scrub_none_parameters
    - ansible.module_utils.common.validation.check_mutually_exclusive
    - ansible.module_utils.common.validation.check_required_arguments
    - ansible.module_utils.common.validation.check_required_if
    - ansible_collections.amazon.aws.plugins.module_utils.botocore.boto3_conn
    - ansible_collections.amazon.aws.plugins.module_utils.botocore.get_waiter
    - ansible_collections.amazon.aws.plugins.module_utils.modules.AnsibleAWSModule
    - ansible_collections.amazon.aws.plugins.module_utils.policy.compare_policies
    - ansible_collections.amazon.aws.plugins.module_utils.retries.AWSRetry
    - ansible_collections.amazon.aws.plugins.module_utils.retries.get_boto3_client_method_parameters
    - ansible_collections.amazon.aws.plugins.module_utils.retries.is_boto3_error_code
    - ansible_collections.amazon.aws.plugins.module_utils.retries.paginated_query_with_retries
    - ansible_collections.amazon.aws.plugins.module_utils.retries.RetryingBotoClientWrapper
    - ansible_collections.amazon.aws.plugins.module_utils.tagging.ansible_dict_to_boto3_tag_list
    - ansible_collections.amazon.aws.plugins.module_utils.tagging.boto3_tag_list_to_ansible_dict
    - ansible_collections.amazon.aws.plugins.module_utils.tagging.compare_aws_tags
    - ansible_collections.amazon.aws.plugins.module_utils.transforms.ansible_dict_to_boto3_filter_list
    - ansible_collections.amazon.aws.plugins.module_utils.transforms.boto3_resource_list_to_ansible_dict
    - ansible_collections.amazon.aws.plugins.module_utils.transforms.boto3_resource_to_ansible_dict
    - ansible_collections.amazon.aws.plugins.module_utils.transforms.sanitize_filters_to_boto3_filter_list
    - ansible_collections.amazon.aws.plugins.module_utils.waiters.wait_with_backoff

- Ensure modules remain idempotent and avoid unnecessary AWS API calls

- Complete the requested implementation before stopping
