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

## Tenanted projects need tenant connections at every lifecycle phase

A project with `TenantedDeploymentMode = "Tenanted"` cannot have a release created unless **at least one tenant is connected to every lifecycle phase's environment** — including phases that will be no-ops for that tenant.

Symptom: `POST /releases` succeeds (release ID is allocated) but the UI shows:

> "Cannot deploy to any of the connected tenants in this phase of the lifecycle"
> "Releases of this project can only be deployed to tenants, but there are no tenants connected to any environments in the current lifecycle phase."

This fires the moment Octopus tries to plan the first phase (Dev) — if no tenant is connected to Dev for that project, planning fails even when the project's deployment steps are scoped to a later env (e.g. `action.environments = ["markets"]`).

**Fix:** for each tenanted project, connect each participating tenant to **every** environment in the lifecycle, not just the env(s) where actual deploy steps will run. The mock steps still skip the no-op phases via `action.environments`, but the tenant-to-env wiring satisfies Octopus's release-planning check.

Affects every tenanted project in this demo (holiday-promo-blitz, customer-mobile-app, loyalty-rewards-service, and the Crusty tenant added live by the Acquire Crusty Croissant runbook). All four setup scripts and the runbook were updated to connect tenants to the full 4-env lifecycle.

Alternative: switch `TenantedDeploymentMode` to `"TenantedOrUntenanted"` so untenanted releases can flow through early phases. We chose the connect-all-envs approach because it preserves the cleaner "all deploys are per-tenant" demo narrative.

## Every phase needs at least one matching step

Companion gotcha to the previous one. Connecting tenants to all 4 lifecycle envs gets you past *release planning*, but **creating a deployment** still fails if the target env has no step that runs there:

> "There are no steps to run when deploying releases of holiday-promo-blitz in the Default channel to the Dev environment for 'MMI-AU-Sydney'. This can happen if your deployment process is empty, or review the filters applied to the steps in your deployment process."

If every step in the process is scoped via `action.environments = [<later-env>]`, then earlier phases of the lifecycle have nothing to run and Octopus refuses to create a no-op deployment.

**Fix:** add a server-side "Prepare release" step at position 0 with `Environments: []` (no env filter — runs everywhere) and no target roles. It does a `Write-Host` of release/env/tenant and exits. Cheap, demonstrative, makes every phase non-empty.

Applied to: holiday-promo-blitz (M1), customer-mobile-app (M3), crusty-croissant-pos (M5). loyalty-rewards-service (M4) already had the Verify FinOps Variables step with no env filter, so was naturally fine.

## API key file format

`~/dev/claude/secrets/taniwha.octopus.app/api_key` is a YAML-ish file with named fields. Extract the value with:

```bash
grep '^value:' ~/dev/claude/secrets/taniwha.octopus.app/api_key | awk '{print $2}'
```

Or in Python: read the file, find the line starting with `value:`, split on `:`, strip the value. **Never echo or log the value.** Pass it only as a header via process substitution (`curl -H @<(...)`) so it never appears in `argv`.
