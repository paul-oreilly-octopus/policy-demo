# M0 — Platform Hub Schema Verification

Date: 2026-05-21
Octopus version: **2026.2.11000**, API 3.0.0
Target instance: `taniwha.octopus.app`

## Method

Direct API probing against `/api`, `/api/deploymentfreezes`, and `/api/Spaces-103/*` (the existing PlatformHub-Demo space). Sent minimal POST/PUT requests to discover required fields and enum values from validation errors.

Probe freeze `DeploymentFreezes-1` was created and deleted as part of this verification (no residue).

## Findings

### 1. Deployment Freezes — API-managed, first-class resource

Endpoint: `/api/deploymentfreezes` (instance-level, not space-scoped).

**Schema (from probe response):**

```json
{
  "Id": "DeploymentFreezes-X",
  "Name": "string",
  "Start": "ISO 8601 datetime",
  "End": "ISO 8601 datetime",
  "ProjectEnvironmentScope": { "Projects-X": ["Environments-Y"] },
  "TenantProjectEnvironmentScope": [
    { "TenantId": "Tenants-X", "ProjectId": "Projects-Y", "EnvironmentId": "Environments-Z" }
  ],
  "RecurringSchedule": null | {
    "Type": "Daily" | "Weekly" | "Monthly",
    "Unit": 1,
    "EndType": "Never" | (others TBD),
    "UserUtcOffsetInMinutes": 0,
    "StartDate": "ISO datetime",
    "EndDate": "ISO datetime",
    "EndOnDate": null | "ISO datetime",
    "EndAfterOccurrences": 0,
    "MonthlyScheduleType": null | (TBD),
    "DateOfMonth": null,
    "DayNumberOfMonth": null,
    "DaysOfWeek": [],
    "DayOfWeek": null
  },
  "OwnerId": null | "Spaces-X",
  "Description": null | "string"
}
```

**Scope dimensions confirmed:**

- Project + Environment (via `ProjectEnvironmentScope`)
- Tenant + Project + Environment (via `TenantProjectEnvironmentScope`)
- **By tenant ID, not by tenant tag** — to scope to "all EMEA tenants" we must enumerate `MMI-UK-London` + `Crusty-Croissant-DE-Berlin` by ID
- **No target-tag scoping** — `permanent-break-glass-only` tag is signaling only

**Recurrence:**

- Native support exists ✓
- Types accepted: `Daily`, `Weekly`, `Monthly` (with required field combinations)
- Types rejected: `Cron`, `OnceDaily`, `Custom`, `None`
- **Smallest granularity is Daily** — cannot do sub-hourly cycles natively
- **Implication for M1:** rolling 5-in-10 freeze CANNOT be expressed as a single recurring freeze. Must use the runbook-fallback (option b from the plan)

### 2. Process Templates — CaC-managed, governance via consumption

Endpoint: `/api/Spaces-X/processtemplates` (TBD — not surfaced in space root links, may be hub-only)

Process templates live in the platform_hub repo at `.octopus/process-templates/*.ocl`. Existing repo has 6:

- `database-service-deploy.ocl`
- `deploy-kubernetes-with-yaml.ocl`
- `nodejs-service-deploy.ocl`
- `payment-service-deploy.ocl`
- `python-ml-service-deploy.ocl`
- `standard-go-service-deploy.ocl`

Governance via consumption: if a project includes a `process_template` block in its deployment process OCL, the template's steps are imposed. The template is the policy.

### 3. No native "required step template" or "required variables" policy

The space root link map does **not** include:

- `Policies`
- `Governance`
- `Guardrails`
- `RequiredSteps`
- `RequiredVariables`
- `Compliance`

Only `MachinePolicies` (deployment-target health policies — unrelated to what we mean).

**Conclusion:** in Octopus 2026.2, Platform Hub governance is expressed through **two primitives**:

| Primitive | Enforces | API/CaC |
|---|---|---|
| Deployment Freezes | Time-based and permanent deploy blocks; scoping by project+env+tenant | API + (optionally) hub repo |
| Process Templates | Deployment process structure (steps, ordering, required actions) | Hub repo (CaC) |

There is no policy type for "this project must define variables X and Y" or "this step template must appear in all production processes." Both must be expressed indirectly through Process Templates.

## Implications for the plan

| Pipeline | Original mechanism | Revised mechanism |
|---|---|---|
| **#1** Rolling holiday freeze | Native recurrence | **Runbook fallback** — `Refresh Demo Freeze` runbook on a scheduled trigger, rewrites Start/End every 5 min. Plan already anticipated this fallback path. |
| **#2** Mandatory prod approval | "Required step template" policy | **Process template** `governed-cloud-prod-deploy` that includes the manual intervention step. The `payment-gateway` project starts WITHOUT using this template; "compliance" = adopting the hub template. |
| **#3** Mandatory security scan | "Required step template" policy | Same pattern — process template with scan step. |
| **#4** Required FinOps variables | "Required variables" policy | Process template includes a `Verify FinOps Variables` step that calls `$OctopusVariables[cost_centre, owner_email]` and fails if either is missing. Project compliance = consuming the template. |
| **#5** Tenant-tag-scoped GDPR step | Tag-scoped step requirement | **Two-template strategy**: a base template for non-EMEA, an `gdpr-emea-deploy` template for EMEA. The Crusty Croissant project switches to the EMEA template when EMEA tenant is connected. OR: a single template with a step whose run-condition checks `Octopus.Deployment.Tenant.Tags["Region/EMEA"]`. Lean toward the single-template + run-condition approach. |
| **#6** Audit trail (meta) | unchanged | unchanged — git log on hub repo + Octopus audit log |
| **#7** PCI permanent freeze | Project-scoped freeze | Works natively — `Start: 2026-01-01`, `End: 2099-12-31`, scope: `pci-card-data-vault` project on Cloud-Prod env. Break-glass via separate channel that's NOT subject to the freeze (need to verify how to express channel-exemption — possibly via a separate freeze that excludes Break Glass channel; channel-based scope is not in the freeze schema, may need to scope by environment instead and have Break Glass deploy through a different environment). |

## New open questions for the plan

1. **M7 break-glass mechanism** — the freeze schema does not include `channels` as a scope dimension. Can a freeze be set such that one channel of a project is exempt? Options:
   - (a) Scope freeze to a specific environment, route Break Glass channel through a different environment (clean separation; needs an extra env)
   - (b) Manually create/cancel the freeze when break-glass is invoked (defeats the purpose of policy)
   - (c) Single freeze; break-glass override is a manual "Cancel Freeze" action recorded in audit (most realistic to real-world use, but takes the freeze offline for everyone briefly)
2. **M5 GDPR scoping mechanism** — single-template-with-run-condition vs two-templates. Run-condition is more elegant; two-templates is more visible.
3. **Demo framing** — the original plan implied multiple policy types. Revised reality is two primitives. The demo arc and narration need updating to reflect this honestly. Two-primitive framing is actually simpler to teach but loses some "look how many policy types Platform Hub supports" punch.

## Recommendation

Proceed with M0 foundation (none of this affects the space/env/tenant/target setup), but pause before M1 to update the plan with the revised governance mechanisms.

## Next steps

1. Complete M0 (foundation) — unchanged scope
2. Update `M0-policy-demo-PLAN.md` Risks & Mitigations + per-milestone scope to reflect the two-primitive reality
3. Capture a `governance-primitives` topic in `memory/` so the demo script can lean on it
