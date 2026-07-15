# Role authoring

Conventions for roles in `roles/` that `ansible-lint`/`yamllint` don't enforce. Two flavors —
**manager** (call AWS modules) and **info** (gather facts); layout `tasks/`, `defaults/`,
`meta/`, `README.md`, `molecule/default/`. Match the nearest role.

## Layout and variables

- Prefix input variables with the role name; default resource lists to `[]`.
- Keep `README.md`, `defaults/main.yml`, `meta/main.yml` aligned when changing variables,
  defaults, dependencies, or published facts.
- Every task carries the role-name tag.

## Manager roles

Most are list-driven: the caller supplies `<role>_list` and `tasks/main.yml` loops it; a few
manage one fixed resource with scalar vars. Structure varies — match the nearest role — but for
the list-driven form:

- **Dispatch**: loop `include_tasks` with `apply.tags` (role-name tag) into the file holding the
  module call(s); the file name varies — a single `include.yml`, or files split by operation
  (`present.yml`/`absent.yml`/`info.yml`).
- **Default injection**: per-item `state` defaults to `present` — via `| d('present')`, a
  `product`/`map('combine')` merge into `__<role>_list`, or a `when` guard.
- **Loop var**: per-item `_<singular>` with a `label`; batched loops use `<role>_list | batch(...)`
  with a `__<role>_list` loop var.
- **Guard**: `when` on the item's identifier being defined (skip check mode where a registered
  value is needed).

Module call in the looped task:

- Optional values → `| d(omit)`.
- `purge_*` booleans pinned `| d(true)`/`| d(false)` — never `| d(omit)`.
- Merge a `Name` tag: `tags: "{{ _x.tags | d({}) | combine({'Name': _x.name}) }}"`.
- Register into `__<role>_result` when a later task reuses it.
- `validate_certs: true`.

Single-resource roles call the module once in `main.yml` with scalar vars (`<role>_name`,
`<role>_state`) and `validate_certs: true`.

## Info roles

Call the `_info` module, register `__<role>_query`, then `set_fact` publishes `_<role>_info_list`
(and `_<role>_info_dict` when there's a stable key), defaulting with `| d([])`/`| d({})`. These
`_`-prefixed facts are the role's outputs.

## Naming

- `__<role>_*` — internal scratch (`set_fact` lists, `register` results): `__<role>_list`,
  `__<role>_result`, `__<role>_query`.
- `_<role>_*` — published facts: `_<role>_info_list`, `_<role>_info_dict`.
- `loop_var` — `_<singular>` (e.g. `_topic`); batched loops use `__<role>_list`.
