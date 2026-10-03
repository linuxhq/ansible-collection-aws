---
name: audit
description: Review a group of related modules with the user, fix approved findings, verify, and open a pull request.
---

# audit

Audit one group of related modules at a time, chosen by the user.

The repository's rules win over this checklist.

## Workflow

- Read the agent instructions and every imported rule.
- Branch from an up-to-date default branch.
- Read the group's modules, helpers, roles, and tests in full.
- Find what outside the group depends on it.
- Review each module from every angle below until a pass finds nothing new.
- Verify unclear API behavior with read-only calls or approved test resources.
- Report issues, optimizations, and inconsistencies with evidence.
- Mark breaking changes, open decisions, and anything unverified.
- Fix only what the user approves.
- Add a regression test and changelog entry for each fix.
- Run formatting, lint, sanity, and unit tests.
- Run affected Molecule scenarios one at a time.
- Commit, push, and open a pull request; do not merge.

## Checklist

### Rules

- Follows every imported rule.
- Matches upstream projects the rules reference.
- Matches sibling modules.

### Inputs

- Options behave like their API parameters.
- Omitted options leave resources unchanged.
- Comparison-only values are never sent.
- Inputs keep the API's naming and accepted values.
- No options for unsupported parameters.

### State

- A second run reports no change.
- Outside changes converge or fail clearly.
- Unchangeable attributes fail before any modification.
- Every status is handled, including failed and deleting.
- Waits end on terminal states within their timeout.
- Reused names and tokens work after a delete.

### Lookups

- Name lookups handle duplicates, foreign owners, and mid-run deletes.
- Info modules return empty results when nothing matches.
- Manager modules fail on missing required resources.
- Manager modules report no change for already-absent resources.

### Check mode and failures

- Check mode predicts the real result and changes nothing.
- The next run converges after a partial failure.
- Failures name the operation, resource, and blocker.

### Results and docs

- Result keys follow the naming convention; values are unchanged.
- User-defined keys keep their case at every level.
- Docs match options, defaults, and return values.
- Version requirements are checked and documented.

### Maintenance

- No redundant API calls or duplicated code.
- No dead options, unused imports, or split strings.

### Roles

- Role behavior is unchanged unless a module fix requires it.
- Existing conditions, defaults, and skips stay as they are.
- Other role changes are proposed, not made.
- Optional inputs pass through without forced values.
- Role docs follow the repository's rules.

### Tests

- Unit tests cover each behavior change.
- Changelog entries match the change; breaking changes are marked.

### Molecule

- Scenarios run every stage to completion.
- Scenarios run one at a time, never alongside others.
- No branch switches or edits while a scenario runs.
- Verify asserts changed behavior, including absent and empty cases.
- Dependent scenarios rerun when a shared role changes.
- Teardown polls for deletion instead of pausing.
- Non-reusable names are unique per run.
- Scenarios do not depend on earlier runs.
- No test resources remain afterward.
- No secrets in facts, logs, or output.
