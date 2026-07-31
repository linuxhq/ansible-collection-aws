# SDK role patterns

SDK-specific patterns for roles that call modules built on `AnsibleAWSModule`. These supplement the
generic conventions in `role-authoring.md`.

## Module call

- Set `validate_certs: true`.
- Pin `purge_*` booleans with `| d(true)` or `| d(false)` — never `| d(omit)`.
- Merge a `Name` tag into the resource's tags:
  - `tags: "{{ _x.tags | d({}) | combine({'Name': _x.name}) }}"`

