---
name: collection-build
description: Build the collection tarball.
---

# collection-build

Run from the collection root (where `galaxy.yml` lives).

```sh
source venv/bin/activate
collection_artifact_dir="$(mktemp -d)"
ansible-galaxy collection build --force --output-path "${collection_artifact_dir}"
```

- Reads `galaxy.yml` (version, `build_ignore`).
- Local builds only **verify** the artifact — they don't publish.
- Release is tag-driven: `.github/workflows/release.yml` builds then publishes. Don't `publish`
  by hand.
- Before tagging: bump `version` in `galaxy.yml`, and record changes with the `changelog` skill.
- Inspect the file list with `tar tzf` and `MANIFEST.json` with `tar xOf`; verify the artifact's
  version and collection dependencies. Don't commit the tarball.

## Dependencies

- `virtualenv` skill
