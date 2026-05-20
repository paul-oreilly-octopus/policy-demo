# Policy Demo — Implementation Plan

## Goals

Build a self-contained Octopus Deploy demo space, themed around **Muffin Man Inc**, that demonstrates 7 different Platform Hub governance scenarios. Each scenario is a deployment pipeline deliberately blocked by one specific policy, with a live "fix and ship" flow. Optimised for a 25-30 minute live customer demo with platform engineering leaders and technical buyers.

**Non-goals:**

- Real application code (every deployment step is a mock script)
- Real cloud infrastructure (Cloud Region targets stand in for stores and backends)
- Production-grade ops (no monitoring, scaling, real secrets management beyond what's needed for the demo to function)

## Architecture summary

See [`CLAUDE.md`](./CLAUDE.md) for the complete architecture. Key elements:

- **Space:** `PolicyDemo` on `taniwha.octopus.app`
- **Demo framing:** two governance primitives — Deployment Freezes (API-managed) and Process Templates (CaC in hub repo). All seven pipelines compose these two primitives.
- **Environments (5):** `Dev → Test → Cloud-Prod → Markets` (Markets tenanted, required), plus `Cloud-Prod-BreakGlass` (untenanted, sits parallel to Cloud-Prod for #7's break-glass path)
- **Lifecycles (3):** `Standard Release`, `PCI Standard`, `PCI BreakGlass`
- **Tenants:** 4 markets at setup time + 1 acquired tenant added live during demo
- **Tag sets:** Region (APAC/EMEA/AMER), Acquisition (native/acquired-crusty)
- **Cloud Region targets:** 6 corporate backends (one in both Cloud-Prod and Cloud-Prod-BreakGlass) + 5 stores (one created live)
- **Platform Hub:** new process templates added to `github.com/paul-oreilly-octopus/taniwha.platform_hub` under `.octopus/process-templates/`; deployment freezes managed via API (not CaC)
- **Mock release & demo reset:** runbooks on a separate `Management` project (Admin project group), driven by a `svc-policy-demo` service account
- **7 demo pipelines:** see CLAUDE.md table

## Milestones

### M0 — Foundation

**Scope:**

- Create `PolicyDemo` space on `taniwha.octopus.app`, connect to existing Platform Hub
- Environments (Dev / Test / Cloud-Prod / Markets), lifecycle (`Standard Release`), project groups (Default / Admin)
- Tag sets (`Region`, `Acquisition`)
- 4 native tenants (NZ, AU, UK, US) with tag application
- 10 Cloud Region targets (6 corp backends, 4 stores) with tags and tenant connections — *note: `store-de-berlin-01` is **not** created here; it's created live during M5*
- `Management` project in Admin project group, untenanted, Default Lifecycle
- `svc-policy-demo` service account + `Mock Release Service Account` team + API key applied to Management
- `Create Demo Releases`, `Reset Demo State` runbooks (basic versions; per-project release logic added in M1-M7)
- **Schema verification:** pull the live Platform Hub state, inspect supported policy types and scope dimensions (especially freeze recurrence, tenant-tag scoping on required-step-template policies, target-tag scoping on freezes)

**Deliverables:**

- `scripts/setup-*.py` for all of the above
- `scripts/octopus_api.py`, `scripts/octopus-api.sh` (copy from oil-vendor-demo)
- `scripts/verify-m0.py` — inventory check, idempotent
- `config/*.json` — resource ID mappings
- Schema-verification notes in `memory/log/m0-schema-verification.md`

**Verification:**

- `verify-m0.py` confirms full inventory present
- Manually invoking `Create Demo Releases` runbook creates a release on every project that exists (none yet — should be a no-op or skip gracefully)
- Cleanup test: `Reset Demo State` runbook leaves M0 inventory intact, only undoes per-pipeline state changes

### M1 — Pipeline 1: rolling holiday freeze

**Mechanism:** Deployment Freeze primitive. Native recurrence is Daily/Weekly/Monthly only, so a runbook rewrites the freeze Start/End on a 5-min schedule to simulate the rolling 5-in-10 cadence.

**Scope:**

- `holiday-promo-blitz` project (tenanted, Markets env, Standard Release lifecycle)
- Two channels: `Default` (subject to rolling freeze), `Break Glass` (skips freeze via different env — TBD, possibly use existing Cloud-Prod-BreakGlass or just allow the freeze to be scoped narrowly to Markets)
- `Refresh Demo Freeze` runbook on Management project (scheduled trigger every 5 min): creates/updates a single `holiday-promo-rolling-freeze` deployment freeze on the `holiday-promo-blitz` project + Markets environment. Cycle: 5 min freeze, 5 min gap, loop.
- `Demo Emergency Responders` team

**Deliverables:**

- `scripts/setup-project-01-holiday.py`
- `scripts/setup-refresh-freeze-runbook.py` (or as part of setup-runbooks.py)
- API-managed freeze (no OCL file needed — freezes are not CaC)

**Verification:**

- During a frozen window: release on Default channel → blocked with clear message naming the freeze
- During an open window: release on Default channel → deploys successfully
- Any time: release on Break Glass channel with justification → deploys; manual intervention recorded; notification logged

### M2 — Pipeline 2: mandatory production approval

**Mechanism:** Process Template primitive. The hub provides `governed-cloud-prod-deploy` template with a mandatory manual-intervention approval step. The project initially uses a basic in-project process (no template).

**Scope:**

- `payment-gateway` project (untenanted, Cloud-Prod env, Standard Release lifecycle)
- Initial process: single "deploy to corp-payments-backend" mock script step — no approval
- New process template in hub repo: `governed-cloud-prod-deploy.ocl` — includes manual intervention step + deploy step
- Demo: project doesn't consume the template; auditor would flag it. Fix is to switch the project's process to `process_template "governed-cloud-prod-deploy" { ... }`.

**Deliverables:**

- `scripts/setup-project-02-payments.py`
- `taniwha.platform_hub/.octopus/process-templates/governed-cloud-prod-deploy.ocl`

**Verification:**

- Baseline release → deploys without approval (visibly missing the gate)
- Switch project to consume the template → next release pauses for approval; deploys after approval
- `Reset Demo State` reverts the project to baseline process

### M3 — Pipeline 3: mandatory security scan

**Mechanism:** Process Template primitive. Hub provides `governed-customer-app-deploy` template with a mandatory security-scan step (runs in Test).

**Scope:**

- `customer-mobile-app` project (tenanted, Cloud-Prod + Markets, Standard Release lifecycle)
- Initial process: deploy step to `corp-mobile-api` + per-tenant rollout to `store` targets, no scan
- New process template in hub repo: `governed-customer-app-deploy.ocl` — includes scan-step + the standard deploy steps
- Step `Security Scan (SBOM + SAST)` runs inline (no separate step template needed, since process templates with inline scripts are cleaner — see process-templates best-practices)

**Deliverables:**

- `scripts/setup-project-03-mobile.py`
- `taniwha.platform_hub/.octopus/process-templates/governed-customer-app-deploy.ocl`

**Verification:**

- Baseline release → deploys without scan
- Switch project to consume template → release runs scan in Test before promoting; deploys
- `Reset Demo State` reverts

### M4 — Pipeline 4: required FinOps tagging variables

**Mechanism:** Process Template primitive. The `governed-customer-app-deploy` template (also used by #3) includes a `Verify FinOps Variables` step that reads `$OctopusVariables[cost_centre, owner_email]` and exits non-zero if either is unset/empty. Project consumes the template; per-tenant variables enforce the FinOps story.

**Scope:**

- `loyalty-rewards-service` project (tenanted, Cloud-Prod backend + Markets per-tenant, Standard Release lifecycle)
- Consumes `governed-customer-app-deploy` template from the start (already governed; this project is the "good citizen" example)
- Per-tenant variables `cost_centre` + `owner_email` set for the 4 native tenants only
- During demo: try to deploy for `Crusty-Croissant-DE-Berlin` tenant (added in M5) → variables missing → `Verify FinOps Variables` step fails → deploy blocked

**Deliverables:**

- `scripts/setup-project-04-loyalty.py`
- The `Verify FinOps Variables` step is part of `governed-customer-app-deploy.ocl` from M3

**Verification:**

- Deploy to NZ tenant (vars set) → ships
- Deploy to Crusty tenant (vars not set) → blocked at verification step with clear "missing variable" message
- Set tenant variables → ships

**Sequencing in demo:** M4 demo segment runs *after* M5's `Acquire Crusty Croissant` runbook (so the Crusty tenant exists). Alternatively, M4 can be standalone if a fifth fictional tenant is created without the required variables.

### M5 — Pipeline 5: GDPR via process template (acquisition reveal)

**Mechanism:** Process Template primitive. Hub provides `eu-region-deploy` template that adds a `GDPR Data Residency Check` step on top of the standard deploy. Step requires `gdpr_data_residency_region` project variable; fails if missing.

The schema gap (no tenant-tag-scoped policy) is bridged by *project consumption*: the EMEA-region project is the one that consumes `eu-region-deploy`. Other projects don't have to. The acquisition demo shows the gap *and* the fix.

**Scope:**

- `crusty-croissant-pos` project (tenanted, Markets via `store` target tag, single tenant in production, Standard Release lifecycle)
- Initial process: basic in-project process (no template) — deliberately non-compliant for an EU-region acquisition
- New process template in hub repo: `eu-region-deploy.ocl` — includes `GDPR Data Residency Check` step + standard deploy
- `Acquire Crusty Croissant` runbook on Management project: creates `Crusty-Croissant-DE-Berlin` tenant (with Region=EMEA, Acquisition=acquired-crusty tags), creates `store-de-berlin-01` target, connects target+tenant+project

**Deliverables:**

- `scripts/setup-project-05-acquired.py` (creates project, **not** the tenant)
- `scripts/setup-acquisition-runbook.py` (or fold into setup-runbooks.py) — adds the `Acquire Crusty Croissant` runbook
- `taniwha.platform_hub/.octopus/process-templates/eu-region-deploy.ocl`

**Verification:**

- Pre-acquisition: project exists, no connected tenants → deploys are no-ops
- Run `Acquire Crusty Croissant` runbook → tenant + target + project connection created
- Try deploy to new tenant with baseline process → deploys WITHOUT GDPR validation (visibly bad)
- Switch project to consume `eu-region-deploy` template → next deploy fires GDPR step → fails on missing `gdpr_data_residency_region` variable
- Set the variable to `EU-CENTRAL-1` → deploys with GDPR validation logged
- `Reset Demo State` removes tenant + target + reverts project process

**Demo narrative:** The audience sees the gap first (non-compliant deploy succeeds, no GDPR check), then the platform-team-driven fix (consume the hub template), then the second block (variable missing), then the final fix (set the variable). Two visible failure modes, one of which is "you can ship without protection but it's visibly absent" — a more honest story than "auto-blocked by tag-scoping."

### M6 — Audit trail walkthrough

**Scope:** no new infrastructure. Documentation + presenter notes for the closing demo segment.

**Deliverables:**

- `memory/m6-audit-trail-walkthrough.md` — script with exact `git log` commands, Octopus audit log filters, mock Slack messages to show
- Confirmation that all M1-M5, M7 policy commits in the platform hub repo are properly authored, signed, and have meaningful commit messages (audit-quality)
- Octopus audit log demo: filter to today, demonstrate finding the break-glass override from M7
- Slack/webhook stub: a file written to `/tmp/policy-demo-notifications.log` (or similar) that the presenter can `tail -f` on a second screen during the demo

**Verification:** dry-run the audit walkthrough, all commands work, all entries visible

### M7 — Pipeline 7: permanent freeze + break-glass via channel-routed environments

**Mechanism:** Deployment Freeze primitive + channel-routed environments (decision option A). The freeze is scoped to project + `Cloud-Prod` env; the Break Glass channel uses a different lifecycle (`PCI BreakGlass`) that deploys to `Cloud-Prod-BreakGlass` env, which is not subject to the freeze.

**Scope:**

- `pci-card-data-vault` project (untenanted, deploys to `corp-pci-vault` target)
- Project lifecycle: default is `PCI Standard` (Dev → Test → Cloud-Prod)
- Two channels:
  - `Default` — uses `PCI Standard` lifecycle (Cloud-Prod)
  - `Break Glass` — uses `PCI BreakGlass` lifecycle (Cloud-Prod-BreakGlass), with version rule that requires a `pci_change_ticket` variable matching `CHG\d{7}`
- Deployment process: deploy mock script step (runs on both channels), plus a manual-intervention step on Break Glass channel only (responsible team: `PCI Change Approvers`), plus a post-deploy notification step that appends to `/tmp/policy-demo-notifications.log` on Break Glass channel only
- Permanent freeze (via API): Start `2026-01-01`, End `2099-12-31`, scope: `pci-card-data-vault` project on Cloud-Prod env (only)
- `PCI Change Approvers` team

**Deliverables:**

- `scripts/setup-project-07-pci.py`
- `scripts/setup-pci-permanent-freeze.py` (calls `/api/deploymentfreezes`)
- `scripts/setup-pci-approvers-team.py`
- No CaC OCL for the freeze (freezes are API-managed in 2026.2)

**Verification:**

- Default channel release → blocked at Cloud-Prod with clear freeze message
- Break Glass channel release without `pci_change_ticket` → blocked at the variable validation
- Break Glass channel release with valid ticket → pauses for PCI Change Approvers manual intervention → on approval, deploys to Cloud-Prod-BreakGlass → notification appended to log → audit entry visible

**Note on the target:** `corp-pci-vault` is reachable from both `Cloud-Prod` and `Cloud-Prod-BreakGlass` environments. Same physical target, two environment memberships. This is what makes the channel-routing work cleanly.

### M8 — Reset-Demo-State runbook

**Scope:** enrich the basic `Reset Demo State` runbook from M0 with per-pipeline logic now that all 7 pipelines exist.

**Reset operations:**

- Remove the manual intervention step from `payment-gateway` (M2)
- Remove the security-scan step from `customer-mobile-app` (M3)
- Clear `cost_centre` / `owner_email` for the Crusty tenant on `loyalty-rewards-service` (M4)
- Delete the `Crusty-Croissant-DE-Berlin` tenant + `store-de-berlin-01` target (M5)
- Remove the GDPR step from `crusty-croissant-pos` if added during demo (M5)
- Cancel any in-progress break-glass deployments on `pci-card-data-vault` (M7)
- Cancel any in-progress break-glass deployments on `holiday-promo-blitz` (M1)
- Clear any per-release variables set during demo (justifications, CHG tickets)

**Deliverables:**

- Updated `scripts/setup-runbooks.py` and/or new `scripts/setup-reset-runbook.py`
- Dry-run capability: `Reset Demo State` accepts a `dry_run=true` parameter that logs what would change without doing it

**Verification:**

- Run full demo end-to-end, then run reset, then verify all 7 pipelines are back at their M1-M7 baseline state

### M9 — Demo script + dry-run

**Scope:**

- Write `memory/m9-demo-script.md` — the 25-30 min presenter script
- Per-segment: timing, talking points, exact UI clicks, fallback if something breaks
- Pre-demo checklist (verify rolling freeze is active, Slack webhook responding, no leftover state)
- Run a full end-to-end dry-run, time each segment, refine timings
- Capture screenshots of key moments for the slide deck

**Deliverables:**

- `memory/m9-demo-script.md`
- `screenshots/` directory with key UI moments
- `memory/m9-dry-run-notes.md` — timing data and refinements

**Verification:** complete dry-run with a colleague observing, fits in 30 min without rushing, all fallback paths tested

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Platform Hub policy schema doesn't support tenant-tag scoping for required-step-templates | M0 verifies upfront; fall back to project-scoped policy for M5 |
| Native cron recurrence not supported on freeze policies | Runbook + scheduled trigger fallback (option b) already designed |
| Step templates are space-scoped (can't be inherited from Platform Hub) | Already known — step templates are created in PolicyDemo space; policy *references* them by ID/version |
| Hub policies for required step templates may need the template to exist in *every* governed space | If so, document and create copies; demo space is only one anyway so impact is small |
| `Acquire Crusty Croissant` runbook timing during demo (audience watches loading spinners) | Pre-warm: have the runbook create everything except the final "connect tenant to project" — that last step is the visible reveal |
| Break-glass demo on `pci-card-data-vault` requires a second user account for the approver | Pre-create a `demo-pci-approver` user; presenter opens a second incognito window |

## Decisions resolved

| # | Decision | Outcome |
|---|---|---|
| 1 | Pipeline #7 mechanism | **Option A** — permanent freeze on Cloud-Prod env (project-scoped); Break Glass channel uses `PCI BreakGlass` lifecycle that deploys to `Cloud-Prod-BreakGlass` env, which is not frozen |
| 2 | Verify hub policy schema before writing OCL | Done in M0; revealed 2 primitives (Freezes + Process Templates), no separate policy framework |
| 3 | Use tenants? | Yes — 4 native + 1 acquired (created live during demo) |
| 4 | Audience framing | Platform engineers + technical buyers |
| 5 | Pipeline #6 (audit trail) | Meta segment at close, not a forced blocked pipeline |
| 6 | Pipeline #1 freeze cadence | Rolling 5-in-10 via runbook (native recurrence is Daily-min only) |
| 7 | Tenant model | Market-based; Region + Acquisition tag sets only |
| 8 | Crusty Croissant tenant creation | Live during demo via `Acquire Crusty Croissant` runbook |
| 9 | Demo framing | **Two governance primitives** (Deployment Freezes + Process Templates) — honest, simpler narrative |
| 10 | Required-step / required-variables enforcement | Via Process Template consumption — there is no separate policy type for these in 2026.2 |

## Open decisions for M0 kick-off — resolved

| Decision | Outcome |
|---|---|
| Setup-script repo location | `github.com/paul-oreilly-octopus/policy-demo`, SSH via `github-octopus` alias |
| Break-glass notification channel | Local log `/tmp/policy-demo-notifications.log`; real Slack integration deferred to FUTURE.md |
| Auth for Platform Hub repo writes | SSH key already in place (`~/.ssh/github.octopus.paul`, used by `github-octopus` SSH alias) |
