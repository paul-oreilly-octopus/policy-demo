# Policy Demo — Memory Index

Topic-organised learnings from building and running the Muffin Man Inc Policy Demo. One line per topic file.

## Topics

- [Octopus 2026.2 API gotchas](gotchas-octopus.md) — freezes are instance-level (not space-scoped), runbook triggers use `EnvironmentIds` not `TargetEnvironmentIds`, snapshot names must be unique, runbooks need `Environments: [...]` to run, etc.

## Conventions

- Topic files live in `memory/<topic>.md`
- Each topic file has frontmatter: `name`, `description`, `type`
- Session logs live in `memory/log/`
- Run `/reflect-logs` periodically to distil logs into topic files
