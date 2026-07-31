# Role authoring

Conventions for the roles in `roles/` that `ansible-lint` and `yamllint` don't enforce on their
own. As with modules, match the nearest existing role.

Roles come in two kinds:

- **Manager** roles call modules to create and update resources.
- **Info** roles gather facts and publish them.

Both share the same layout: `defaults/`, `meta/`, `molecule/default/`, `README.md`, `tasks/`.

## Layout and variables

- Prefix a role's input variables with the role name.
- Choose defaults by behavior, not only by type. List-driven roles normally default their public
  list to `[]`; use `null`, `[]`, or `{}` only when that value accurately represents "unset" or
  "empty" for the role.
- Keep these in sync when you change variables, defaults, dependencies, or published facts:
  - `README.md`
  - `defaults/main.yml`
  - `meta/main.yml`
  - the Molecule scenario
- Tag every task with the role name.

## Manager roles

Most manager roles are list-driven: the caller passes a `{{ role }}_list`, and `tasks/main.yml`
loops over it. Match the nearest role; the list-driven pattern works like this.

### Dispatch

- Loop directly on the module when each item needs one task.
- Use `include_tasks` when an item needs multiple tasks, operation-specific files, or branching.
  Set `apply.tags` to the role-name tag so tagged runs still reach the child tasks.
- Keep `present` and `absent` behavior explicit. When a role supports both states, exercise both in
  Molecule.

### Default state

- Default each item's `state` to `present` when unset, via one of:
  - `| d('present')`
  - a `product`/`combine` merge into an internal `__{{ role }}_list`
  - a `when` guard

### Loop

- Loop with a per-item `loop_var` named `_{{ singular }}` and a `label`.
- Batch only when it provides actual concurrency with `async`, satisfies an API limit, or is part
  of a module's request shape. A synchronous one-item module loop does not need `batch`.
- Guard the loop with a `when` on the item's identifier.

### Module call

- Default optional values with `| d(omit)`.
- Pin `purge_*` booleans with `| d(true)` or `| d(false)` — never `| d(omit)`.
- Merge a `Name` tag into the resource's tags:
  - `tags: "{{ _x.tags | d({}) | combine({'Name': _x.name}) }}"`
- Set `validate_certs: true`.
- Register `__{{ role }}_result` if a later task needs it.
- Preserve the module's native `changed` result. Add `changed_when` only when the module cannot
  report the intended behavior itself; remove async-era overrides when converting a task to a
  synchronous call.

### Optional inputs

- Do not infer that an input is required merely because the README or Molecule scenario supplies
  it. Requiredness comes from the role or module contract.
- When making an input optional, retain useful documented examples and positive tests. Add a case
  that omits the input or passes its valid empty value.

### Single-resource roles

- Skip the list; call the module once in `main.yml`.
- Use scalar variables:
  - `{{ role }}_name`
  - `{{ role }}_state`
- Set `validate_certs: true`.

## Info roles

- An info role's public output is its `_` prefixed facts.
- Call the matching info module and register the result as `__{{ role }}_query`.
- Use `set_fact` to publish snake_case facts, defaulting the source with `| d([])` or `| d({})`:
  - `_{{ role }}_info_list`
  - `_{{ role }}_info_dict` (when the data has a stable key)

## Meta dependencies

- Add an info role as a meta dependency when a manager consumes its published inventory facts,
  including facts referenced inside nested dictionaries.
- Pass the manager role's tag through the dependency so tagged runs include it.
- Keep dependency declarations and the README dependency list in sync.
- Info roles intended for reuse as dependencies set `allow_duplicates: true`.

## Molecule safety

See the `molecule` skill for safety rules, credential handling, and cleanup.

## Naming

| Prefix            | For              | Examples                                                         |
| ----------------- | ---------------- | ---------------------------------------------------------------- |
| `_{{ role }}_`    | Published facts  | `_{{ role }}_info_list`, `_{{ role }}_info_dict`                 |
| `_{{ singular }}` | `loop_var`       | `_topic` (batched loops reuse `__{{ role }}_list`)               |
| `__{{ role }}_`   | Internal scratch | `__{{ role }}_list`, `__{{ role }}_result`, `__{{ role }}_query` |
