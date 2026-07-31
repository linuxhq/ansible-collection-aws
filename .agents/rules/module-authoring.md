# Module authoring

Conventions for the resource and info modules in `plugins/modules/`. This is house style, not a
strict spec:

- When in doubt, match the nearest existing module.
- Prefer the shared `module_utils` helpers over writing your own logic.

## Structure

Modules usually come as a manager/info pair — `{{ module }}.py` and `{{ module }}_info.py` — though not
every resource has both. Lay each file out in this order:

- `DOCUMENTATION`, `EXAMPLES`, and `RETURN` docstrings.
- Imports.
- Helpers, by module type:
  - Manager → `ensure_present`, `ensure_absent`.
  - Info → `list`, `info`.
- `main()` — builds the module, dispatches on `state`, and calls the helpers.

When starting a new module, copy the structure of an existing pair. Separate logical steps within
a function with single blank lines; one blank line at most.

## Behavior

### State

- Keep the `present` and `absent` flows explicit and easy to follow.
- Stay idempotent: read the current state first, and skip API calls that aren't needed.

### Check mode

- Set `supports_check_mode=True`.
- Guard every mutating API call so that none run while `module.check_mode` is set.
- Still return the correct `changed` value and result shape without making the change.
- Info modules always report `changed=False`.

### Tags and waiters

- Compare desired against current tags before any change.
- For long-running operations, expose the same wait controls as nearby modules.
- Use the collection's waiter helpers instead of writing your own polling loop.

## Arguments

- Accept parameters and return data in snake_case; convert to API shapes with the collection's
  helpers.
- Mark secrets with `no_log=True`, and keep their values out of examples, return data, and error
  messages.

### Validation

- Prefer the appropriate argument-spec validator over a hand-written check when the corresponding
  relationship exists:
  - `mutually_exclusive`
  - `required_by`
  - `required_if`
  - `required_one_of`
  - `required_together`
- For "one of several forms" cases — such as `id`, or `name` plus `parent_id` — use several
  `required_one_of` entries that each pair with the standalone identifier.
- Put constraints on a nested dict option inside that option's own `argument_spec`.
- Document each validation rule in the descriptions of the options it affects. For an option
  that's only sometimes required, document the condition instead of setting `required: true`.

### Info lookups

- Only offer a singular lookup (`name`, `id`, or other unique identifier) when the API itself
  accepts one — don't emulate it with plural parameters.
- If the singular lookup and the list/filter options drive different API calls, make the two
  modes mutually exclusive.
- Document the split: `O(name)` is mutually exclusive with the list filters, and any option used
  only by the singular lookup should note that it `Requires O(name)`.

## Operations

- Create the client with a retry decorator.
- Use the collection's pagination helper for paginated list/describe calls.
- Clean request dicts of unset parameters before the call.
- On an API failure, include the resource's name or identifier in the error.
- Normalize API responses with the collection's helpers before returning them via `exit_json`.

## Documentation

Keep `DOCUMENTATION` and `argument_spec` in lockstep, and keep `RETURN` aligned with the actual
result. `EXAMPLES` should demonstrate representative supported inputs; an optional input may remain
in examples after it stops being required.

- Use `extends_documentation_fragment` matching the nearest module.
- Give list options and list return values an `elements` entry.
- Write `EXAMPLES` using the fully-qualified collection name, `{{ namespace }}.{{ name }}.{{ plugin }}`.
- Reference nested options with paths like `O(ip_addresses[].ipv6)`.
