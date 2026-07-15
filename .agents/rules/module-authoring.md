# Module authoring

Conventions for resource and `_info` modules in `plugins/modules/` (built on `AnsibleAWSModule`;
lookup plugins don't apply). Prevailing house style, not a hard spec — match the nearest module
and prefer existing `module_utils` helpers (`helpers.md`) over new logic.

## Structure

Resource modules usually come as a manager/`_info` pair (`<module>.py` + `<module>_info.py`),
not always both. Per file: `DOCUMENTATION`/`EXAMPLES`/`RETURN` r-strings, imports,
`ensure_present`/`ensure_absent` (or list/info) helpers, then `main()` (builds the module,
dispatches on `state`, calls the helpers). Model a new module on an existing pair.

## Behavior

- Keep `present`/`absent` flows explicit; keep modules idempotent (read current state, avoid
  needless API calls).
- Check mode: `supports_check_mode=True`, no mutating calls under `module.check_mode`, still
  return the predicted result shape. Info modules return `changed=False`.
- Tags: use the tagging helpers; `compare_aws_tags` before any tag call; honor `purge_tags` only
  when `tags` is given.
- Long-running ops: expose wait controls like nearby modules; use the waiter helpers, not custom
  polling.

## Arguments

- snake_case params; transform to boto3 shapes with existing helpers.
- Prefer `AnsibleAWSModule` validation args (`required_by`, `required_if`, `required_one_of`,
  `required_together`, `mutually_exclusive`) over manual checks. For compound alternatives (e.g.
  `id` vs `name`+`parent_id`), use multiple `required_one_of` sharing the standalone identifier.
- Nested dict options: put per-item constraints (e.g. `mutually_exclusive`) inside the nested
  `argument_spec`.
- Secrets: `no_log=True`; keep values out of examples, returns, and errors.
- Info modules: expose singular lookups (`name`/`id`/`arn`) only when the API takes a singular
  identifier — don't fake it with plural params. If singular and list/filter modes drive
  different API paths, make them mutually exclusive.

## Operations

- Clients: `module.client("<svc>", retry_decorator=AWSRetry.jittered_backoff())`, then
  `aws_retry=True` on calls. Use `paginated_query_with_retries` for paginated list/describe
  (it retries internally — no `aws_retry`); hand-roll a marker loop only when no paginator exists.
- Gate newer SDK APIs in `main()` with `get_boto3_client_method_parameters()` before dispatch;
  keep it local to `main()` and `fail_json()` naming the unsupported method/parameter.
- `scrub_none_parameters` before a mutating boto3 call built from optional params.
- Wrap failures with `module.fail_json_aws`, including the resource identifier.

## Result data

- Return snake_case; normalize boto3 responses with the transformation helpers before
  `exit_json`.
