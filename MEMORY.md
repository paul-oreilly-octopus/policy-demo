# Policy Demo — Memory Index

Topic-organised learnings from building and running the Muffin Man Inc Policy Demo. One line per topic file.

## Topics

- [Octopus 2026.2 API gotchas](gotchas-octopus.md) — freezes are instance-level (not space-scoped), runbook triggers use `EnvironmentIds` not `TargetEnvironmentIds`, snapshot names must be unique, runbooks need `Environments: [...]` to run, **Platform Hub Policy OCL schema (Rego in conditions/scope blocks)**, **feature-toggle discovery for missing-feature triage**
- [M6 audit trail walkthrough](m6-audit-trail-walkthrough.md) — closing demo segment commands
- [M9 demo script](m9-demo-script.md) — 25-30 min presenter script (three-primitive framing)

## Conventions

- Topic files live in `memory/<topic>.md`
- Each topic file has frontmatter: `name`, `description`, `type`
- Session logs live in `memory/log/`
- Run `/reflect-logs` periodically to distil logs into topic files
