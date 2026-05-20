# CLAUDE.md — Policy Demo

## Overview

Mock Octopus Deploy environment demonstrating **Platform Hub governance** through seven blocked-pipeline scenarios. Theme: **Muffin Man Inc**, a global QSR chain that recently acquired **Crusty Croissant Co** (German bakery).

This is **not a real application** — Cloud Region targets stand in for real infrastructure, deploy steps are mock scripts that log what they would do.

Models the runbook-driven mock-release pattern from `oil-vendor-demo` so the demo is repeatable and resettable.

## Demo framing: two governance primitives

Octopus 2026.2 Platform Hub exposes **two** primitives for centrally governing many spaces and projects:

1. **Deployment Freezes** — API-managed time-based or permanent blocks on deployments. Scope dimensions: Project + Environment, or Tenant + Project + Environment. Native recurrence supports Daily / Weekly / Monthly cycles.
2. **Process Templates** — CaC-managed shared deployment processes. Consuming projects inherit the steps. The template *is* the policy — when a project consumes a hub template, the included steps (approvals, scans, validators) are enforced.

The demo's seven pipelines compose these two primitives many ways. There is **no separate "required step template" or "required variables" policy type** — all such enforcement flows through a Process Template that the project consumes.

## Architecture

### The fictional company: Muffin Man Inc

Global QSR chain. NZ-founded, operates in NZ/AU/UK/US. Recently acquired Crusty Croissant Co (German bakery chain, EMEA region). Engineering owns the digital platform: POS, mobile ordering, loyalty, payments, marketing/promos, and the PCI cardholder data vault.

### Octopus instance

- **Server:** `https://taniwha.octopus.app`
- **Space:** `PolicyDemo` (ID TBD on M0 creation) — Muffin Man Inc
- **Platform Hub repo:** existing `github.com/paul-oreilly-octopus/taniwha.platform_hub` — policies go into `.octopus/policies/`
- **API key:** `~/dev/claude/secrets/taniwha.octopus.app/api_key` (read-only)

### Environments (5)

| Environment | Purpose | Tenanted? |
|---|---|---|
| `Dev` | Engineering | Untenanted |
| `Test` | QA | Untenanted |
| `Cloud-Prod` | Corporate backends — payment-gateway, pci-card-data-vault (Default channel) | Untenanted |
| `Cloud-Prod-BreakGlass` | Break-glass-only path for pci-card-data-vault (Break Glass channel). Exists so the permanent freeze on `Cloud-Prod` can be sidestepped via channel-routing, without the freeze schema needing to express channel-exemption. | Untenanted |
| `Markets` | Per-market deployments — promos, mobile app, loyalty, POS | Tenanted, required |

### Lifecycles (3)

| Lifecycle | Phases | Used by |
|---|---|---|
| `Standard Release` | `Dev → Test → Cloud-Prod → Markets` | Tenanted projects: holiday-promo-blitz, customer-mobile-app, loyalty-rewards-service, crusty-croissant-pos. Also payment-gateway (Cloud-Prod final). |
| `PCI Standard` | `Dev → Test → Cloud-Prod` | pci-card-data-vault Default channel |
| `PCI BreakGlass` | `Dev → Test → Cloud-Prod-BreakGlass` | pci-card-data-vault Break Glass channel |

Manual gate at the last phase of each lifecycle.

### Tenants (4 + 1 added during demo)

| Tenant | Region tag | Acquisition tag | Notes |
|---|---|---|---|
| `MMI-NZ-Auckland` | APAC | native | Founding market |
| `MMI-AU-Sydney` | APAC | native | |
| `MMI-UK-London` | EMEA | native | |
| `MMI-US-NewYork` | AMER | native | |
| `Crusty-Croissant-DE-Berlin` | EMEA | acquired-crusty | **Created live during demo (M5 reveal)** |

### Tag sets (2)

| Tag set | Tags | Cardinality | Purpose |
|---|---|---|---|
| `Region` | APAC, EMEA, AMER | single-value | Scopes GDPR policy (#5) |
| `Acquisition` | native, acquired-crusty | multi-value | Storytelling + slicing |

### Cloud Region targets

| Target | Environment(s) | Target tags | Connected tenants |
|---|---|---|---|
| `corp-pos-backend` | Cloud-Prod | `corp-backend` | — |
| `corp-payments-backend` | Cloud-Prod | `corp-backend` | — |
| `corp-mobile-api` | Cloud-Prod | `corp-backend` | — |
| `corp-loyalty` | Cloud-Prod | `corp-backend` | — |
| `corp-marketing` | Cloud-Prod | `corp-backend` | — |
| `corp-pci-vault` | Cloud-Prod, Cloud-Prod-BreakGlass | `corp-backend`, `permanent-break-glass-only` | — |
| `store-nz-auckland-01` | Markets | `store` | `MMI-NZ-Auckland` |
| `store-au-sydney-01` | Markets | `store` | `MMI-AU-Sydney` |
| `store-uk-london-01` | Markets | `store` | `MMI-UK-London` |
| `store-us-newyork-01` | Markets | `store` | `MMI-US-NewYork` |
| `store-de-berlin-01` | Markets | `store` | `Crusty-Croissant-DE-Berlin` (added live) |

The `permanent-break-glass-only` tag is signaling only — there's no policy that reads it. The Octopus 2026.2 freeze schema does not support target-tag scoping. The tag is documentation: "this target is locked down, deploys to it use the Break Glass path."

### Project groups

| Project group | Projects | Purpose |
|---|---|---|
| Default | All 7 demo pipelines | Deployment projects |
| Admin | Management | Runbooks (mock releases, demo reset, Crusty acquisition) |

### The 7 demo pipelines

Each project is **deliberately non-compliant** at setup; demo flow is: try to deploy → blocked → fix → ship.

| # | Project | Tenanted | Primitive | Mechanism | Block | Fix |
|---|---|---|---|---|---|---|
| 1 | `holiday-promo-blitz` | Yes | Deployment Freeze | Runbook-driven 5-in-10 rolling freeze on Markets env (native recurrence is daily-min, so a runbook rewrites Start/End every 5 min) | Currently frozen | Wait, or use the project's Break Glass channel + justification |
| 2 | `payment-gateway` | No | Process Template | Project initially uses a basic "deploy" process. Hub provides `governed-cloud-prod-deploy` template with mandatory manual-intervention approval step. | Project doesn't consume the template — auditor flags it | Consume the hub template |
| 3 | `customer-mobile-app` | Yes | Process Template | Hub provides `governed-customer-app-deploy` template with mandatory security-scan step | Project doesn't consume the template | Consume the hub template |
| 4 | `loyalty-rewards-service` | Yes | Process Template | Hub provides `governed-customer-app-deploy` template that includes a `Verify FinOps Variables` step which fails if `cost_centre` or `owner_email` aren't set | Crusty tenant has neither variable set | Set tenant variables |
| 5 | `crusty-croissant-pos` | Yes (one tenant) | Process Template | Hub provides `eu-region-deploy` template with a GDPR-data-residency step. Step always runs and requires `gdpr_data_residency_region` variable. | Project doesn't consume `eu-region-deploy` (currently uses base template — visibly skips GDPR for an EU tenant) | Switch project to consume `eu-region-deploy` → block at variable check → set variable → ships |
| 6 | — (meta segment) | — | — | Audit trail walkthrough — git log on hub repo + Octopus audit log + tail of notification log | — | — |
| 7 | `pci-card-data-vault` | No | Deployment Freeze + Channel-routed environments | Permanent freeze (2026 → 2099) on Cloud-Prod env for this project. Two channels: Default deploys to Cloud-Prod (frozen), Break Glass deploys to Cloud-Prod-BreakGlass (not frozen). | Default channel → frozen at Cloud-Prod | Use Break Glass channel; requires `pci_change_ticket` (CHG\d{7}), `PCI Change Approvers` team approval, post-deploy notification |

### Break-glass mechanism

The freeze schema does not support per-channel exemption. The pattern: **route a Break Glass channel through a different environment that is not subject to the freeze.**

For #1 (rolling freeze on Markets): the rolling freeze is scoped only to the Markets env phases the runbook touches. A Break Glass channel on `holiday-promo-blitz` is wired (optional path — demo segment #1 may simply wait out the freeze rather than override it; this channel exists for completeness and is the fallback if the demo runs short on a frozen window).

For #7 (permanent freeze on Cloud-Prod): the permanent freeze is scoped to the Cloud-Prod environment only. The Break Glass channel uses the `PCI BreakGlass` lifecycle which deploys to `Cloud-Prod-BreakGlass` instead. That environment has no freeze on it.

Requirements to use the Break Glass channel on either project:

1. Release created on `Break Glass` channel
2. `emergency_justification` variable set (free text, min length) — or `pci_change_ticket` matching `CHG\d{7}` for #7
3. Manual intervention completed by an authorised team (`Demo Emergency Responders` for #1, `PCI Change Approvers` for #7)
4. Post-deploy script appends to `/tmp/policy-demo-notifications.log` recording the override (a Slack/webhook stub — see FUTURE.md)

### Teams

| Team | Roles | Purpose |
|---|---|---|
| `Demo Read-Only` | Project Viewer, Environment Viewer | Stakeholder observers |
| `Demo Full Authority` | Project Lead, Project Deployer, Runbook Producer, Tenant Manager | SRE / operators |
| `Demo Emergency Responders` | Project Deployer, can complete break-glass interventions on #1 | Override the rolling freeze |
| `PCI Change Approvers` | Can complete break-glass intervention on #7 | Approve PCI vault deploys |
| `Customer Demo Viewers` | Project Viewer + Runbook Consumer scoped to Management only | Audience accounts — read processes, run reset runbook, cannot edit |
| `Mock Release Service Account` (team) | Holds `svc-policy-demo` user, scoped roles | Runbook automation |

### Runbooks (all on `Management` project, Admin group)

| Runbook | Purpose |
|---|---|
| `Create Demo Releases` | One release on each of the 7 projects (sensible SemVer bumps) |
| `Acquire Crusty Croissant` | Live during M5 demo: creates the `Crusty-Croissant-DE-Berlin` tenant, applies tags, creates `store-de-berlin-01` target, connects to `crusty-croissant-pos` |
| `Reset Demo State` | Restore all 7 projects to their non-compliant baseline; remove acquired tenant + target; clear any in-demo variables |
| `Refresh Demo Freeze` *(if needed)* | Rewrites the rolling freeze window every 10 min — only used if Platform Hub native recurrence isn't supported |

Plus one scheduled trigger for `Refresh Demo Freeze` if option (b) is needed (see M1 plan).

### Service accounts

| Username | Type | Used by | API key location |
|---|---|---|---|
| `svc-policy-demo` | Service (`IsService: true`) | Mock release + reset + acquisition runbooks | `OctopusApiKey` sensitive variable on `Management` project (set at provision time, never written to disk) |

The full-admin key in `~/dev/claude/secrets/taniwha.octopus.app/api_key` is used only by setup scripts. It is **never** stored in Octopus or used at runtime.

## Repository structure

```
policy-demo/
  ABOUT.md
  CLAUDE.md                          # this file
  MEMORY.md                          # learnings index
  FUTURE.md                          # backlog
  README.md                          # human-readable overview
  M0-policy-demo-PLAN.md             # full implementation plan
  scripts/
    octopus_api.py                   # shared Python API helper (copy from oil-vendor-demo)
    octopus-api.sh                   # shared bash API helper
    setup-space.py                   # create PolicyDemo space, connect to Platform Hub
    setup-foundation.py              # envs + lifecycle + project groups
    setup-tag-sets.py                # Region + Acquisition tag sets
    setup-tenants.py                 # 4 native tenants + tag application
    setup-targets.py                 # 10 cloud-region targets + tags + tenant connections
    setup-management-project.py      # Management project + service account
    setup-runbooks.py                # Create Demo Releases, Acquire Crusty, Reset Demo State
    setup-project-01-holiday.py      # holiday-promo-blitz
    setup-project-02-payments.py     # payment-gateway
    setup-project-03-mobile.py       # customer-mobile-app
    setup-project-04-loyalty.py      # loyalty-rewards-service
    setup-project-05-acquired.py     # crusty-croissant-pos
    setup-project-07-pci.py          # pci-card-data-vault
    push-platform-hub-policies.py    # writes OCL files to taniwha.platform_hub repo
    verify-m0.py                     # foundation inventory check
  config/
    foundation-ids.json              # env/lifecycle/tagset/space IDs
    tenants.json                     # tenant IDs + tags
    targets.json                     # target IDs + tags + tenant connections
    projects.json                    # project + channel + team IDs
    service-account.json             # svc-policy-demo IDs (no values)
  memory/
    log/                             # session logs
    gotchas-octopus.md               # Octopus + Platform Hub gotchas (created when first one captured)
  context/                           # active work context
```

## Conventions

- Follow general conventions from `~/dev/claude/CLAUDE.md`
- API helper uses `curl -H @<(...)` process substitution to keep the API key out of `argv`
- All deployment steps are mock PowerShell that logs target/channel/environment/version
- Setup scripts are **idempotent** — safe to re-run; check for existing resources by name before creating
- Resource IDs saved to `config/*.json` after creation
- Platform Hub OCL files committed to `taniwha.platform_hub` via the `push-platform-hub-policies.py` script (HTTPS PAT auth)
- Tag set updates **never** drop existing tags — additive only

## Common operations

### Run setup scripts (M0 foundation)

```bash
cd ~/dev/claude/octopus/policy-demo
./scripts/setup-space.py
./scripts/setup-foundation.py
./scripts/setup-tag-sets.py
./scripts/setup-tenants.py
./scripts/setup-targets.py
./scripts/setup-management-project.py
./scripts/setup-runbooks.py
./scripts/verify-m0.py
```

### Manual API call

```bash
source scripts/octopus-api.sh
octopus_get "/tenants" | python3 -m json.tool
```

### Push policies to Platform Hub

```bash
./scripts/push-platform-hub-policies.py
```

Clones `taniwha.platform_hub`, adds/updates `.octopus/policies/*.ocl`, commits and pushes.

## Source control

- **Setup-script repo (this directory):** `github.com/paul-oreilly-octopus/policy-demo` — SSH via `github-octopus` alias (key `~/.ssh/github.octopus.paul`)
- **Platform Hub repo:** existing `github.com/paul-oreilly-octopus/taniwha.platform_hub` — same SSH alias. Octopus Server already has its own HTTPS PAT-based GitConnection configured to pull from this repo (set up for `PlatformHub-Demo` and reused here); our scripts push policy OCL changes via SSH and Octopus picks them up on next sync.
- **Demo space CaC:** not enabled initially. May convert after M9 if it makes the audit-trail story stronger.

## Notifications (break-glass)

Demo notifications are written to a local log file `/tmp/policy-demo-notifications.log`. During a live demo, presenter `tail -f`s this file on a second screen.

Real Slack/webhook integration is intentionally deferred — see [`FUTURE.md`](./FUTURE.md).

## Demo audience

Platform engineering leads and technical buyers evaluating Platform Hub for governance use cases. Lean into Git/OCL workflow, audit trail, composability. Not pitched at compliance officers (that's a separate angle).
