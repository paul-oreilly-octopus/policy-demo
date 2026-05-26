---
name: gotchas-octopus
description: Octopus Deploy 2026.2 API gotchas discovered building the Policy Demo
type: project
---

# Octopus 2026.2 API gotchas

API quirks and non-obvious shapes hit while building the Policy Demo. Useful for future scripts against the same instance.

## Deployment Freezes are instance-level, not space-scoped

The endpoint is `/api/deploymentfreezes`, not `/api/{spaceId}/deploymentfreezes`. Calling the space-scoped path returns 404 silently.

**Why it matters:** if you're building a `space_id`-based helper that prepends every path, deployment-freeze calls need an "instance bypass" (use `iget`/`ipost` from `octopus_api.py`, not the space-scoped variants).

**How to apply:** all freeze CRUD goes through `o.iget("/deploymentfreezes")`, `o.ipost("/deploymentfreezes", ...)`, etc. The freeze itself can still scope by project IDs that belong to a specific space — instance-level just means the endpoint isn't space-bucketed.

## Runbook triggers use `EnvironmentIds`, not `TargetEnvironmentIds`

Creating a runbook scheduled trigger via `POST /api/{spaceId}/projecttriggers` requires the action shape:

```json
{
  "Action": {
    "ActionType": "RunRunbook",
    "RunbookId": "Runbooks-X",
    "EnvironmentIds": ["Environments-Y"],   // ✓ correct
    "TenantIds": [], "TenantTags": []
  }
}
```

`TargetEnvironmentIds` is silently ignored and the API returns "Please select at least one environment for this runbook trigger". The error message doesn't hint at the field-name mismatch.

## Runbook snapshot names must be unique per runbook

`POST /runbookSnapshots?publish=true` with `Name: "Snapshot 1"` succeeds the first time and fails on every re-run with "RunbookSnapshot 'Snapshot 1' already exists for this project."

**Workaround:** generate a unique name on each publish (we use `Auto-{UTC timestamp}`), or use Octopus's auto-increment mask `Snapshot #{Octopus.Runbook.NextSnapshotIncrement}`. We picked timestamp names because they're naturally sortable and signal "auto-published, not hand-named."

## Runbooks need both `EnvironmentScope: Specified` and `Environments: [...]`

Creating a runbook with `EnvironmentScope: "Specified"` and `Environments: []` succeeds, but every attempt to run it (manually or via scheduled trigger) returns "Runbook cannot be executed for environment Environments-X. Please check your runbook Environment settings."

The runbook's allowed environments list must include the env the trigger or manual run targets. For the freeze-refresh runbook we set `Environments: [Dev]` since the runbook doesn't actually care about its execution env (it just hits the freeze API), and `Dev` is the natural "admin-y" choice.

## Runbook runs require `RunbookSnapshotId` AND a published snapshot

`POST /runbookRuns` with just `RunbookId` returns "The RunbookSnapshotId field is required." The published snapshot ID is on the runbook resource: `GET /runbooks/{id}` → `PublishedRunbookSnapshotId`.

Triggers automatically use whatever is currently published, but manual API runs must specify it explicitly.

## Space creation requires a non-empty manager list

`POST /api/spaces` with `SpaceManagersTeamMembers: []` rejects with "select either teams and/or users as managers." Always include the current user (`GET /users/me`) as a manager.

## Platform Hub Policy OCL schema

Discovered after the initial schema verification missed it. The `compliance-policy-test-evaluation` feature toggle gates the *evaluation engine* — not the authoring path. Policies can be authored (UI or hand-written OCL) and committed to the hub repo even when the engine is off; they show "inactive" in the UI until evaluation is enabled.

File location: `.octopus/policies/<slug_with_underscores>.ocl`. The filename slug must match the Rego `package` directive inside.

Top-level OCL blocks:

```
name = "policy-name-with-dashes"    # display name
violation_action = "warn" | "block" # how Octopus reacts when result.allowed=false

conditions {
    rego = <<-EOT
        package <slug_with_underscores>

        default result := {"allowed": false, "reason": "..."}

        result := {"allowed": true} if { ... }
    EOT
}

scope {
    rego = <<-EOT
        package <same_slug>

        default evaluate := false   # or true for "all deployments"

        evaluate if {
            input.Project.Slug == "..."
            input.Environment.Name == "..."
        }
    EOT
}
```

Rego inputs (confirmed):
- `input.Steps` — array, each with `Id`, `Name`, `ActionType`
- `input.SkippedSteps` — array of step IDs being skipped
- `input.Environment.Name` — environment name
- `input.Space.Id` — space ID
- `input.Project.Slug` — project slug
- `input.Tenant.Tags` — array of canonical tag strings (e.g. `"Region/EMEA"`)
- `input.Variables.<name>` — resolved project variables for the current scope

Default for `result` is `{"allowed": false}` — policies are deny-by-default; the conditions block describes when to *allow*. The `violation_action = "warn"` keeps it observable without blocking; `"block"` enforces hard.

Schema discovered by reading `/.octopus/policies/manual_approval_for_prod_deploy.ocl` authored via the UI starter wizard. There's no API endpoint surfaced under `/api/policies` even when the engine is enabled — they're CaC-only.

## Feature-toggle discovery

When the API surface seems to be missing a feature documented elsewhere, check `/api/configuration/feature-toggles` BEFORE concluding the feature is absent. Toggles starting with `compliance-`, `platform-hub-`, or named after a feature category often gate visibility of an entire endpoint family.

In this case the `compliance-policy-test-evaluation` toggle was disabled, hiding the policy-evaluation engine from the API. Authoring still worked through the UI/Git path. Future me: always grep feature-toggles when a feature seems missing.

## Policies can't see inside consumed process templates

When a project consumes a hub process template, the template's internal steps are NOT inlined into the project's deployment process. Instead, a single step appears in `input.Steps` with:

- `step.ActionType == "Octopus.ProcessTemplate"`
- `step.Source.Type == "Process Template"`
- `step.Source.SlugOrId == "<template-slug>"`

The template's contents — the Security Scan step, the Manual Intervention, the GDPR check, etc. — are not visible to the policy engine. Policies that check for inline step names or `Octopus.Manual` actions will MISS the same step when it's provided by a template.

**Fix pattern:** a step-checking policy needs TWO allow rules:

1. Match an inline step (original logic — name contains "Security Scan", `ActionType == "Octopus.Manual"`, etc.)
2. Match a template-reference step whose `Source.SlugOrId` is in a whitelist of templates known to provide the required step

```rego
security_scan_templates := {"governed-customer-app-deploy"}

result := {"allowed": true} if {
    some step in input.Steps
    contains(step.Name, "Security Scan")
    not step.Id in input.SkippedSteps
}

result := {"allowed": true} if {
    some step in input.Steps
    step.Source.Type == "Process Template"
    step.Source.SlugOrId in security_scan_templates
    not step.Id in input.SkippedSteps
}
```

The whitelist is explicit and auditable — adding a new compliant template is a one-line policy change with a Git commit attached.

Variable-checking policies (e.g. `required-finops-variables` which reads `input.Variables.cost_centre`) are unaffected — they evaluate post-resolution, so values set by the project, by tenant scope, or by template parameter substitution are all visible the same way.

## Consuming a process template doesn't remove existing inline steps

When you add a Platform Hub process template to a project's deployment process, the new template step is **appended** to the existing steps — it doesn't replace them. If the project had a baseline process before, those steps are still there alongside the template reference. The deployment will run the template AND the baseline.

For demos where the "fix" is to switch from baseline to template, the operator has to manually delete the baseline steps after adding the template. Otherwise the audit log will show both ran. Worth noting in the demo script.

## Process templates: publish ≠ share (sharing is UI-only)

A parsed/published template will load fine into the Platform Hub library but will NOT appear in any space's process editor until that template has been explicitly **shared** with the space. Publish and share are two different actions:

| Action | Path | API support |
|---|---|---|
| Publish | `git push` to the hub repo containing the OCL file | implicit via Git sync |
| Share with space | UI: Platform Hub → Process Templates → \<template\> → Sharing tab → add space | **none** — there is no REST API for this in 2026.2 |

The sharing list is stored as a database relationship inside Octopus, deliberately *not* in the template OCL (so authors can't accidentally hand all spaces access via a Git commit). Setup scripts CANNOT automate sharing. After every new template is added to the hub repo, a human must visit the UI and toggle the share for each consuming space.

Symptom: process editor's "Add step from Platform Hub" picker shows nothing (or shows old templates but not new ones). The newly-pushed templates exist but are not shared with the space you're editing in.

**Fix:** UI → Platform Hub → Process Templates → open each template → Sharing tab → add the consuming space → Save.

## Process templates can't env-scope steps in OCL

Process templates live in the hub repo and are space-agnostic. They're loaded/parsed BEFORE being applied to any consuming space, so the OCL parser has no environment list to resolve slugs against. Adding `environments = ["cloud-prod"]` (or `"test"`, `"markets"`, etc.) inside an action block fails at load time:

> "Error mapping from slugs to IDs. ProcessTemplate.Steps[N].Actions[0].Environments[0] has unknown slug 'cloud-prod'"

**Fix:** drop `environments = [...]` from process-template action blocks entirely. Express env-scoping through target roles + the consuming project's lifecycle instead. If a step needs targets, its `Octopus.Action.TargetRoles` parameter (typically pointed at a role like `corp-backend` or `store`) constrains where it runs because those roles only exist on targets in specific envs. Server-side steps (manual intervention, script with `RunOnServer=true`, no targets) run in every phase of the consuming project's lifecycle.

**Implication:** a manual-intervention step in a hub template will fire at *every* env the consuming project's lifecycle includes — not just Cloud-Prod. That's strictly more governance than originally intended (audit-friendly) but worth knowing for demo pacing.

## Process templates: every action needs `worker_pool_variable` set

The "Every step needs a worker pool" note already in this file (from the process-templates best-practices) bites even for `Octopus.Manual` actions that don't actually need a worker. Setting `worker_pool_variable = ""` causes:

> "There was an error trying to parse the file '.octopus/...'. A step must specify a worker pool parameter"

**Fix:** set `worker_pool_variable = "worker_pool"` (pointing at the standard `worker_pool` parameter every template declares) on EVERY action — even manual interventions. The runtime ignores it for `Octopus.Manual` but the OCL validator requires it.

## Tenanted projects need tenant connections at every lifecycle phase

A project with `TenantedDeploymentMode = "Tenanted"` cannot have a release created unless **at least one tenant is connected to every lifecycle phase's environment** — including phases that will be no-ops for that tenant.

Symptom: `POST /releases` succeeds (release ID is allocated) but the UI shows:

> "Cannot deploy to any of the connected tenants in this phase of the lifecycle"
> "Releases of this project can only be deployed to tenants, but there are no tenants connected to any environments in the current lifecycle phase."

This fires the moment Octopus tries to plan the first phase (Dev) — if no tenant is connected to Dev for that project, planning fails even when the project's deployment steps are scoped to a later env (e.g. `action.environments = ["markets"]`).

**Fix:** for each tenanted project, connect each participating tenant to **every** environment in the lifecycle, not just the env(s) where actual deploy steps will run. The mock steps still skip the no-op phases via `action.environments`, but the tenant-to-env wiring satisfies Octopus's release-planning check.

Affects every tenanted project in this demo (holiday-promo-blitz, customer-mobile-app, loyalty-rewards-service, and the Crusty tenant added live by the Acquire Crusty Croissant runbook). All four setup scripts and the runbook were updated to connect tenants to the full 4-env lifecycle.

Alternative: switch `TenantedDeploymentMode` to `"TenantedOrUntenanted"` so untenanted releases can flow through early phases. We chose the connect-all-envs approach because it preserves the cleaner "all deploys are per-tenant" demo narrative.

## Every phase needs at least one matching step (any project, not just tenanted)

Octopus refuses to create a deployment when the target env has no step that runs there. Symptom (tenanted *or* untenanted projects):

> "There are no steps to run when deploying releases of <project> in the Default channel to the Dev environment. This can happen if your deployment process is empty, or review the filters applied to the steps in your deployment process."

If every step in the process is scoped via `action.environments = [<later-env>]`, the earlier phases of the lifecycle have nothing to run and Octopus refuses to create a no-op deployment. This is NOT tenancy-related — the previous gotcha (tenants at every phase) is a separate issue that happens earlier (at release-planning time on tenanted projects). Once you're past planning, the empty-phase check still fires.

**Fix:** add a server-side "Prepare release" step at position 0 with `Environments: []` (no env filter — runs everywhere) and no target roles. It does a `Write-Host` of release/env/tenant and exits. Cheap, demonstrative, makes every phase non-empty.

Applied to:
- holiday-promo-blitz (M1, tenanted)
- payment-gateway (M2, **untenanted** — proving this is not a tenancy gotcha)
- customer-mobile-app (M3, tenanted)
- crusty-croissant-pos (M5, tenanted)

loyalty-rewards-service (M4) already had the Verify FinOps Variables step with no env filter, so was naturally fine.

## API key file format

`~/dev/claude/secrets/taniwha.octopus.app/api_key` is a YAML-ish file with named fields. Extract the value with:

```bash
grep '^value:' ~/dev/claude/secrets/taniwha.octopus.app/api_key | awk '{print $2}'
```

Or in Python: read the file, find the line starting with `value:`, split on `:`, strip the value. **Never echo or log the value.** Pass it only as a header via process substitution (`curl -H @<(...)`) so it never appears in `argv`.
