# Module authoring

Conventions for the resource and info modules in `plugins/modules/` (built on
`AnsibleAWSModule`; lookup plugins are out of scope). This is house style, not a strict spec:

- When in doubt, match the nearest existing module.
- Prefer the shared `module_utils` helpers (see `helpers.md`) over writing your own logic.

## Structure

Modules usually come as a manager/info pair — `{{ module }}.py` and `{{ module }}_info.py` — though not
every resource has both. Lay each file out in this order:

- `DOCUMENTATION`, `EXAMPLES`, and `RETURN` docstrings.
- Imports.
- Helpers, by module type:
  - Manager → `ensure_present`, `ensure_absent`.
  - Info → `list`, `info`.
- `main()` — builds the `AnsibleAWSModule`, dispatches on `state`, and calls the helpers.

When starting a new module, copy the structure of an existing pair.

## Behavior

### State

- Keep the `present` and `absent` flows explicit and easy to follow.
- Stay idempotent: read the current state first, and skip API calls that aren't needed.

### Check mode

- Set `supports_check_mode=True`.
- Guard every mutating API call so that none run while `module.check_mode` is set.
- Still predict the change: compute and return the same `changed` value and result shape you
  would produce outside check mode.
- Info modules always report `changed=False`.

### Tags

- Manage tags with the tagging helpers (see `helpers.md`).
- Compare desired against current tags with `compare_aws_tags` before any change.
- Apply `purge_tags` only when the caller passed `tags`.

### Waiters

- For long-running operations, expose the same wait controls as nearby modules.
- Use the waiter helpers instead of writing your own polling loop.

## Arguments

### Types

- Accept parameters and return data in snake_case; convert input parameters to boto3 shapes
  with the existing helpers.

### Validation

- Prefer the argument-spec validators over hand-written checks — for every module:
  - `mutually_exclusive`
  - `required_by`
  - `required_if`
  - `required_one_of`
  - `required_together`
- For "one of several forms" cases — such as `id`, or `name` plus `parent_id` — use several
  `required_one_of` entries that each pair with the standalone identifier.
- Put constraints on a nested dict option inside that option's own `argument_spec`.

### Secrets

- Mark secrets with `no_log=True`, and keep their values out of examples, return data, and error
  messages.

### Info lookups

- Only offer a singular lookup (`name`, `id`, `arn`) when the API itself accepts one — don't
  emulate it with plural parameters.
- If the singular lookup and the list/filter options drive different API calls, make the two
  modes mutually exclusive.

## Operations

### Clients and retries

- Create the client with a retry decorator, and pass `aws_retry=True` on the calls that should
  retry: `module.client("{{ service }}", retry_decorator=AWSRetry.jittered_backoff())`.
- For paginated `list`/`describe` calls, use `paginated_query_with_retries`. It retries on its
  own, so don't add `aws_retry`; only write a manual pagination loop when the API has no
  paginator.

### SDK support

- Always check in `main()` with `get_boto3_client_method_parameters()` that the SDK provides the
  methods and parameters the module uses, and `fail_json()` naming any that are missing.

### Requests and failures

- Run request dicts built from optional parameters through `scrub_none_parameters` before the
  call.
- On an API failure, call `module.fail_json_aws` and include the resource's name or identifier.

## Result data

- Normalize boto3 responses with the transformation helpers before returning them via
  `exit_json`.
