# Ansible SDK Plugins

AWS SDK-specific standards for Python modules, lookup plugins, and filter
plugins under `plugins/`. Apply these with `ansible-plugins.md`.

## Scope and naming

- Give each module one AWS resource or closely related operation.
- Follow AWS API boundaries when separating dependent resources.
- Separate many-to-many relationships when one module would obscure ownership.
- Prefix a module name with the boto3 service name that supplies its client.
- Include the managed resource in the name when the service manages several.
- Use established AWS abbreviations only; do not invent shortened names.
- Reserve the `aws_` prefix for broad AWS behavior that has no clear service.

## SDK and module base

- Use boto3 and botocore; never use the retired boto SDK.
- Build every AWS module with `AnsibleAWSModule`.
- Document the reason before using `AnsibleModule` for an AWS module.
- Obtain clients and resources through `module.client()` or `module.resource()`.
- Do not construct boto3 sessions, clients, or resources in individual modules.
- Do not import boto3 directly.
- Import botocore only for named exceptions or types.
- Follow the optional-import pattern; `AnsibleAWSModule` checks SDK availability.
- Confirm SDK behavior against the versions pinned by this repository.

## SDK compatibility

- Keep existing behavior available on the collection's minimum SDK versions.
- Gate only the option or operation that requires a newer SDK feature.
- Use `module.require_botocore_at_least()` for a known version boundary.
- Use `require_client_methods()` when method availability is the compatibility
  boundary.
- Name the missing method, parameter, or feature in a compatibility failure.
- Document the minimum botocore version on every affected option.
- Do not fail unaffected operations because an optional feature is unavailable.

## Interface compatibility

- Preserve existing parameters, defaults, aliases, and return values.
- Treat removing an option, requiring an existing option, changing a default,
  or removing a return value as a breaking change.
- Make breaking changes only in a major release after a practical deprecation.
- Return a replacement key alongside its deprecated predecessor.
- Add a changelog fragment for every behavior change and bug fix.

## Documentation fragments and defaults

- SDK-backed plugins extend `amazon.aws.boto3`.
- AWS-connected modules use `amazon.aws.common.modules`.
- Other AWS-connected plugin types use `amazon.aws.common.plugins`.
- Region-aware modules use `amazon.aws.region.modules`.
- Region-aware non-module plugins use `amazon.aws.region.plugins`.
- Plugins that manage tags extend `amazon.aws.tags`.
- Do not redefine options supplied by a documentation fragment.
- Add modules to the repository's AWS action group in `meta/runtime.yml` when
  they must share AWS `module_defaults`.

## Requests and idempotency

- Do not modify an AWS attribute when its option was not explicitly supplied.
- Make an explicitly supplied option converge to the requested value.
- Default collection, association, and tag behavior to replacement.
- Add an explicit additive option only when callers require additive behavior.
- Remove unset values with `scrub_none_parameters` before an SDK call.
- Preserve AWS field meanings when mapping module options to SDK parameters.
- Declare IAM policy inputs with `type="json"`.
- Compare IAM policies with `compare_policies`; ignore ordering differences.

## Clients, retries, and pagination

- Create service clients with `AWSRetry.jittered_backoff()`.
- Pass `aws_retry=True` to calls that need throttling protection.
- Add only modeled transient or eventual-consistency codes to retry handling.
- Retry the failing API operation, not an unrelated readiness check.
- Keep retry counts and delays bounded.
- Prefix caller-configurable retry controls with `backoff_`.
- Use `paginated_query_with_retries` for supported paginated operations.
- Do not add `aws_retry` to `paginated_query_with_retries`; it retries calls.
- Write manual pagination only when botocore exposes no paginator.

## Waiters

- Use `get_waiter` and `wait_for_resource_state` when a waiter exists.
- Do not replace an available waiter with a custom polling loop.
- Expose wait controls only for a concrete long-running operation.
- Match the wait option names and defaults of the nearest AWS module.

## Exceptions and failures

- Wrap every boto3 and botocore call at the boundary that can explain it.
- Use `is_boto3_error_code()` only when a specific code changes control flow.
- Catch remaining `BotoCoreError` and `ClientError` failures.
- Report SDK failures through `module.fail_json_aws()`.
- Include the attempted operation and resource identifier in the message.
- Let retry decorators observe retryable errors before converting them.
- Do not branch on an exception's rendered message.

## Tags

- Define `tags` as a dictionary with an unset default.
- Define `purge_tags` as a Boolean that defaults to `true`.
- Leave tags unchanged when the caller omits `tags`.
- Remove absent tags only when `tags` is supplied and `purge_tags` is true.
- Treat an explicit empty `tags` dictionary as a request to remove all tags.
- Convert SDK tag lists with `boto3_tag_list_to_ansible_dict`.
- Convert desired tags with `ansible_dict_to_boto3_tag_list` when required.
- Calculate tag changes with `compare_aws_tags` before mutating AWS.
- Return tags as a case-preserving dictionary, never an SDK list.

## Results

- Convert SDK response keys with `camel_dict_to_snake_dict`.
- Preserve case-sensitive tag keys while converting surrounding response data.
- Keep the meaning of AWS response fields; change only their key casing.
- Name the top-level resource result after the managed resource.
- Return multiple info results as a list of dictionaries.
- Return a singular info result as a dictionary.
- Return an empty list when a plural info query finds no resources.
- Match reusable return keys to manager-module options or aliases.
- Preserve replaced return keys through a documented deprecation period.

## Testing

- Unit-test isolated transformations, comparisons, and SDK error handling.
- Keep unit tests offline and use pytest without `unittest.TestCase` classes.
- Isolate SDK calls in focused functions and mock their results, not boto3
  internals.
- Pass the module object only when a helper uses its API; otherwise pass values.
- Add AWS integration coverage for every new module.
- Place integration tests under `tests/integration/targets/<module>/`.
- Add an aliases file that places AWS tests in the `cloud/aws` group.
- Cover key API calls and assert documented return fields.
- Name test resources with `resource_prefix` or `tiny_prefix`.
- Create resources in the provided `aws_region` and always clean them up.
- Supply AWS test credentials through the AWS `module_defaults` group.
- Request only the IAM permissions exercised by the integration test.
- Exercise the earliest supported SDK unless the tested feature requires a
  documented newer version.
