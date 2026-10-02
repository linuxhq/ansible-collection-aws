---
name: audit
description: Review a group of related modules with the user, fix approved findings, verify, and open a pull request.
---

# audit

Audit one group of related modules at a time, such as every module, role, and test
that shares a name prefix. The user picks the group; work through it with them.

## Workflow

1. Read the repository's agent instructions and every rule they import before
   reviewing anything. Findings and fixes follow those rules.
2. Create a branch for the group from an up-to-date default branch.
3. Read every module, shared helper, role, integration test, and unit test in the
   group in full, and find what outside the group depends on it.
4. Review each module from every angle in the checklist below. Read it again from a
   different angle; keep going until a pass finds nothing new.
5. Report findings as issues, optimizations, and inconsistencies. For each, give the
   module, the failure scenario, the evidence, and the proposed fix. Mark breaking
   changes and anything that needs a decision. Say what was not verified.
6. Wait for the user. Fix only what they approve.
7. Add a focused regression test for each fix, and a changelog entry if the
   repository uses them.
8. Run the repository's formatting, lint, sanity, and unit test tooling.
9. Run each affected integration test one at a time. Do not switch branches or edit
   files while a test runs. Confirm no test resources remain afterward.
10. Commit, push, and open a pull request. Do not merge.

When the API's behavior is unclear from its schema or documentation, check it with
read-only calls, or with throwaway resources the user approves and that are cleaned
up afterward. Do not report anything as fine without evidence.

Where this checklist and the repository's rules differ, the rules win.

## Checklist

### Rules and conventions

- [ ] The change follows every rule the repository's agent instructions import.
- [ ] Behavior matches the upstream projects the rules point to.
- [ ] Sibling modules handle the same situation the same way.

### Inputs and requests

- [ ] Each option behaves like the API parameter it maps to: required, optional,
      defaults, limits, allowed values, and errors.
- [ ] An omitted option leaves an existing resource unchanged; no module default
      overrides a value the user did not set.
- [ ] Values used only for comparison or matching are never sent in a request.
- [ ] Inputs keep the API's naming; validation does not reject values the API accepts.
- [ ] Options exist only for parameters the API supports.

### State and idempotence

- [ ] A second run with the same input reports no change.
- [ ] Changes made outside the module are detected and converged, or fail clearly.
- [ ] Attributes that cannot change, or change only in one way, fail clearly before
      any modification.
- [ ] Every status the API can return is handled, including transitional, failed,
      and deleting states of the resource and its children.
- [ ] Waits end on terminal states and stay within their timeout.
- [ ] Identifiers and idempotency tokens behave correctly when reused after a delete.

### Lookups

- [ ] Lookups by name handle duplicates, resources owned by someone else or by the
      platform, eventual consistency, and resources deleted mid-run.
- [ ] Information modules return an empty result when nothing matches.
- [ ] Management modules fail when an explicitly identified resource is missing and
      must exist, and report no change when it should be absent.

### Check mode and failures

- [ ] Check mode predicts the result a real run would produce and changes nothing.
- [ ] After a partial failure, the next run converges.
- [ ] Failure messages name the operation, the resource, and any blocking dependency.

### Results and documentation

- [ ] Result keys follow the repository's naming convention and values are
      unchanged; user-defined keys, such as tags and property maps, keep their case
      at every nesting level.
- [ ] Documented options, defaults, return values, and nested fields match the code.
- [ ] Version requirements are checked in code and documented on the affected option.

### Efficiency and maintenance

- [ ] No redundant API calls, repeated reads, or duplicated code.
- [ ] No dead options, unused imports, or split string literals.

### Roles and tests

- [ ] Roles pass optional inputs through without forcing a value and keep their
      documented contract.
- [ ] Role documentation changes follow the repository's rules.
- [ ] Unit tests cover each behavior change.
- [ ] Integration tests exercise the changed paths, and pass.
- [ ] Changelog entries match the change, with breaking changes marked.
