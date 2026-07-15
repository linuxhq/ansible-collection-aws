# Module documentation

Keep `DOCUMENTATION`, `EXAMPLES`, `RETURN`, and `argument_spec` in lockstep — every option,
return field, alias, choice, and default must agree across all four.

- `extends_documentation_fragment` the standard fragments for common options, region, and
  boto3, as the nearest module does.
- List options/returns: include `elements`.
- `EXAMPLES` use the collection FQCN (`<namespace>.<name>.<plugin_name>`).
- Document every validation rule (`mutually_exclusive`, `required_by`, `required_if`,
  `required_together`, `required_one_of`) in the affected options. For conditionally required
  options, document the condition instead of `required: true`. Use nested refs like
  `O(ip_addresses[].ipv6)` inside list elements.
- Info modules with both singular and list/filter options: document the split — `O(name)` is
  mutually exclusive with list filters; singular-only options say `Requires O(name)`.
