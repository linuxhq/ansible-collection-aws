# AGENTS.md

## Model

gpt-5.5 high

## Standards

* Support check mode

* Support state of present and absent

* Support async patterns where operations may take significant time

* Ensure task descriptions are consistent across roles; majority convention wins

* Ensure task descriptions are consistent across molecule tests; majority convention wins

* Ensure role description matches between README.md and meta/main.yml

* Prefer ansible builtin modules over command or shell

* Keep implementations simple, idempotent, and consistent across roles

* Use fully qualified collection names (FQCN)

* Complete the requested implementation before stopping
