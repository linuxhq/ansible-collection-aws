# SDK module patterns

SDK-specific patterns for modules built on `AnsibleAWSModule` (in `main()`). These supplement
the generic conventions in `module-authoring.md`.

## Tags

- Manage tags with the tagging helpers (see `helpers-sdk.md`).
- Compare desired against current tags with `compare_aws_tags` before any change.

## Clients and retries

- Create the client with a retry decorator, and pass `aws_retry=True` on the calls that should
  retry: `module.client("{{ service }}", retry_decorator=AWSRetry.jittered_backoff())`.
- Add modeled eventual-consistency error codes to the retry decorator when the service returns a
  retryable 4xx error. Retry the failing API call itself; a readiness check on a related resource
  does not guarantee that the service can already retrieve it.
- For paginated `list`/`describe` calls, use `paginated_query_with_retries`. It retries on its
  own, so don't add `aws_retry`; only write a manual pagination loop when the API has no
  paginator.
- Check in `main()` with `get_boto3_client_method_parameters()` when the module uses methods or
  parameters that may be absent from the collection's minimum supported SDK, and `fail_json()`
  naming any that are missing.

## Requests and results

- Run request dicts through `scrub_none_parameters` before the call.
- On an API failure, call `module.fail_json_aws` and include the resource's name or identifier.
- Normalize boto3 responses with the transformation helpers before returning them via `exit_json`.
