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

## API key file format

`~/dev/claude/secrets/taniwha.octopus.app/api_key` is a YAML-ish file with named fields. Extract the value with:

```bash
grep '^value:' ~/dev/claude/secrets/taniwha.octopus.app/api_key | awk '{print $2}'
```

Or in Python: read the file, find the line starting with `value:`, split on `:`, strip the value. **Never echo or log the value.** Pass it only as a header via process substitution (`curl -H @<(...)`) so it never appears in `argv`.
