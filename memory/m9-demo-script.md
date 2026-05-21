---
name: m9-demo-script
description: 25-30 min presenter script for the Muffin Man Inc Policy Demo
type: project
---

# Policy Demo — presenter script

25-30 minutes. Platform engineering leaders and technical buyers. Lean into Git/OCL workflow, audit trail, composability. Two-primitive framing: **Deployment Freezes + Process Templates**.

Theme: **Muffin Man Inc** — global QSR chain (NZ/AU/UK/US), recently acquired German bakery **Crusty Croissant Co**.

## Pre-demo checklist (T-10 min)

- [ ] Browser tab on Octopus PolicyDemo space (Projects view)
- [ ] Terminal pane on `~/dev/claude/octopus/taniwha.platform_hub` (for `git log` in segment 7)
- [ ] Refresh Demo Freeze runbook has fired at least once today — check `https://taniwha.octopus.app/app#/Spaces-142/operations/runbooks` → Refresh Demo Freeze should show a recent successful run
- [ ] Confirm rolling freeze is currently active — query: `curl ".../api/deploymentfreezes" -H "X-Octopus-ApiKey: ..."` and check that `holiday-promo-rolling-freeze.End` is in the future
- [ ] All 6 demo projects in PolicyDemo space, baseline (non-compliant) processes intact — re-run `verify-m0.py` style spot-check or just glance at Projects list
- [ ] No leftover Crusty Croissant tenant from a prior demo — run `Reset Demo State` runbook once as a safety net
- [ ] Logged in as a user that's a member of the Prod Change Approvers + PCI Change Approvers teams (so live approvals work without account-switching)
- [ ] Slack/notification stub: nothing to set up — uses Octopus task log output

## Opening (1 min)

> "Octopus Platform Hub gives platform teams **two governance primitives**: deployment freezes and process templates. Today we're going to look at how Muffin Man Inc — a global fast-food chain — uses just these two to enforce *seven different things*. Plus a live acquisition story. Plus the audit trail at the end."

Show the Projects list. Point at the seven projects. Mention Crusty doesn't exist as a tenant yet.

## Segment 1 — Holiday freeze (3 min)

**Pipeline:** `holiday-promo-blitz`

1. Open the project. Show the deployment process — one step, "Deploy promo asset". *"Nothing fancy. Just a marketing rollout. It's compliant by structure."*
2. Click **Create Release** → version `1.0.demo`. Auto-promotes through Dev → Test → Cloud-Prod.
3. Click **Deploy to Markets**, pick MMI-UK-London. Expect: **blocked** with message *"The environment Markets is frozen by holiday-promo-rolling-freeze."*
4. Talking point: *"This is the 'Christmas freeze' pattern. Marketing wants to push, but it's a sensitive window. Here's the freeze."*
5. Open the freeze: Configuration → Deployment Freezes → `holiday-promo-rolling-freeze`. Show scope (project + Markets env), Start/End.
6. *"In production this is one freeze that recurs annually for the holiday window. For the demo I've wired up a 5-min-on, 5-min-off cycle so you can see it actually working. Watch the End time — when it passes, the deploy will succeed."*
7. Wait or punt depending on timing. (Optional: open another tab, try the same deploy 5 min later — succeeds.)

**Fallback if no freeze is active:** trigger the **Refresh Demo Freeze** runbook manually. The next demo attempt will be blocked.

## Segment 2 — Mandatory production approval (4 min)

**Pipeline:** `payment-gateway`

1. Open the project. Show the deployment process — one step, "Deploy to corp-payments-backend". *"This deploys cardholder-adjacent code. No approval. Auditor would have words."*
2. Create Release v1.0.demo. Auto-promotes through Dev → Test → **Cloud-Prod immediately, no gate**. Show how the deploy *just ships* — no approval, no audit point.
3. *"That's the non-compliant state. Now let me show you the platform team's response."*
4. Open the Platform Hub repo (`github.com/paul-oreilly-octopus/taniwha.platform_hub`). Navigate to `.octopus/process-templates/governed-cloud-prod-deploy.ocl`. Walk through:
   - Manual intervention step
   - `ResponsibleTeamIds` parameter
   - The deploy step
5. *"The platform team published this template. It's the single source of truth for 'how to deploy to Cloud-Prod safely.' Any project consuming it inherits the approval step. It can't be removed by the consuming team."*
6. Back in Octopus. Edit payment-gateway's deployment process. **Add step** → from Platform Hub → select `governed-cloud-prod-deploy`. Set parameters (target_role=corp-backend, approver_team_ids=Teams-82 — Prod Change Approvers). Save.
7. Create release v1.0.demo2. Auto-promotes Dev → Test → **Cloud-Prod halts at the manual intervention**. Show the pause.
8. Switch to the Prod Change Approvers UI view (or just approve as the current user if they're a member). Approve. Deploy completes.

## Segment 3 — Mandatory security scan (4 min)

**Pipeline:** `customer-mobile-app`

1. Open the project. Show baseline: backend deploy + store rollout. *"Same idea: deploying a customer-facing app, but no SBOM, no SAST. Just deploy."*
2. Quick release → ships without scans.
3. *"Same playbook. Platform team has a template for this too."*
4. Open `governed-customer-app-deploy.ocl` in the hub repo. Walk through:
   - Security Scan step (SAST + SBOM + image scan, mocked) running server-side in Test only
   - Backend deploy step
   - Per-tenant store rollout step
5. Add to customer-mobile-app: consume `governed-customer-app-deploy`. Set parameters (backend_target_role=corp-backend, store_target_role=store). Save.
6. New release → in Test the scan step fires, logs mocked findings (0 critical, 0 high, 2 medium…). Proceeds. *"Audit-quality. Every release now ships an SBOM."*

## Segment 4 — Acquire Crusty Croissant (5 min)

**The headline reveal.**

1. *"Stepping out of the platform team's perspective for a moment. Muffin Man Inc just announced they're acquiring Crusty Croissant Co, a German bakery chain. The integration starts today. Let's onboard them."*
2. Open Management project → Operations → Runbooks → **Acquire Crusty Croissant**. Run it. Pick Dev env.
3. Wait ~30 seconds. Task succeeds.
4. *"What just happened: new tenant created with Region=EMEA + Acquisition=acquired-crusty tags. Berlin store target created. Tenant connected to three projects."*
5. Show the new tenant in the Tenants view. Show the tag application.
6. Open `crusty-croissant-pos`. Create release v1.0.demo. Auto-promotes. Deploy to **Crusty-Croissant-DE-Berlin**.
7. **Deploy succeeds.** *"Hmm. We just deployed a German customer-data system, and… nothing checked GDPR compliance. The audit team would absolutely flag this."*
8. *"Platform team's response, again. Same playbook."*
9. Open `eu-region-deploy.ocl` in the hub repo. Walk through: GDPR data-residency check + EU allow-list + store rollout.
10. Back in Octopus: edit `crusty-croissant-pos` process → consume `eu-region-deploy`. Save.
11. New release. Deploy to Berlin tenant. **Fails** at GDPR check with *"GDPR enforcement: deployments serving EMEA tenants must declare 'gdpr_data_residency_region'..."*
12. Open project variables. Add `gdpr_data_residency_region` = `EU-CENTRAL-1`. Save.
13. Re-deploy. Ships clean with GDPR validated. *"That's the acquisition pattern: the new tenant inherits all the governance the EMEA region already had. Platform team didn't touch the project — they just published the template once."*

## Segment 5 — FinOps enforcement on the new tenant (3 min)

**Pipeline:** `loyalty-rewards-service`

1. *"Same Crusty tenant. Different pipeline. Watch."*
2. Open `loyalty-rewards-service`. Create release. Deploy to Crusty-Croissant-DE-Berlin.
3. **Fails** at Verify FinOps Variables with *"Policy violation: required FinOps variable(s) not set for tenant 'Crusty-Croissant-DE-Berlin': cost_centre, owner_email."*
4. *"This isn't a separate policy. The loyalty service was already governed. The platform team set FinOps tagging as mandatory ages ago. The native MMI markets all have these variables set per-tenant. The new acquired tenant doesn't — it inherits the **requirement**, not the values."*
5. Open project variables. Add `cost_centre = RETAIL-EU-CRUSTY-001` and `owner_email = crusty-finops@muffinman.co`, scoped to Crusty-Croissant-DE-Berlin tenant.
6. Re-deploy. Ships. *"Two minutes of setup, full FinOps lineage."*

## Segment 6 — PCI break-glass (4 min)

**Pipeline:** `pci-card-data-vault`

1. Open the project. *"This is different. This holds cardholder data. It's permanently frozen on Cloud-Prod. Every. Single. Deploy. Goes through break-glass."*
2. Show the project's permanent freeze: Configuration → Deployment Freezes → `pci-card-data-vault-permanent-freeze`. Show the Start (today) and End (2099). *"Never expires. Never lifts. By design."*
3. Show the two channels: Default and Break Glass.
4. *"Default goes to Cloud-Prod, hits the freeze. Break Glass goes to Cloud-Prod-BreakGlass — a parallel environment that is **not** frozen. That's the channel-routed-environment pattern. The freeze schema doesn't support per-channel exemption, so we route the channel around the freeze by env."*
5. Create release on **Default** channel → blocked at Cloud-Prod by freeze. *"That's the everyday state."*
6. *"Now: P1 security vuln. Need to push a patch right now. Here's break-glass."*
7. Create release on **Break Glass** channel. Set `pci_change_ticket = CHG1234567`. Deploy.
8. At Cloud-Prod-BreakGlass: pauses for manual intervention. Switch to a PCI Change Approvers member (or have a pre-prepared second-screen approver). Approve. Deploy proceeds.
9. Notification step fires. Show the task log:
   ```
   ##NOTIFICATION## BREAK_GLASS_DEPLOY
     project    = pci-card-data-vault
     release    = ...
     ticket     = CHG1234567
     approver   = <user>
     timestamp  = ...
   ```
10. *"In production that's a Slack/PagerDuty entry that security gets paged on. The override is captured. Always."*

## Segment 7 — Audit trail close (3 min)

See `memory/m6-audit-trail-walkthrough.md` for the exact commands.

1. `git log --oneline --since="this morning" -- .octopus/process-templates/` on `taniwha.platform_hub` — show today's policy commits
2. `git show 27d8f05` — drill into one (governed-customer-app-deploy)
3. Octopus → Configuration → Audit, filter to today — show the fresh break-glass deployment from segment 6
4. Highlight the ##NOTIFICATION## line in the task log from earlier
5. *"Three audit surfaces. Git for what the rules are and who wrote them. Octopus for what the rules caught. Slack/log for who got told about exceptions. Auditors don't have to take anyone's word for it — they can verify the whole chain."*

## Close (30 sec)

> "Two primitives — deployment freezes and process templates. Seven different kinds of governance, one tenant onboarded live, one break-glass override executed, full audit trail at the end. That's Platform Hub."

## Recovery moves

| If… | Do… |
|---|---|
| Freeze isn't active when segment 1 starts | Manually run **Refresh Demo Freeze** runbook |
| Approval doesn't fire in segment 2 | Make sure consuming-project's `approver_team_ids` parameter is set to the **actual team ID** (not name) |
| Crusty tenant exists from a prior demo | Run **Reset Demo State** runbook before starting; or skip the "create tenant" step and just connect it to projects |
| FinOps verify fires in segment 4 (mobile-app) when you don't want it to | The mobile-app demo doesn't go through loyalty-rewards-service — they're independent pipelines |
| PCI break-glass doesn't allow you to approve | You're not a member of `PCI Change Approvers` team — add yourself before the demo |
| Wrong tab/window open during the audit trail close | The `git log` always works. Lead with it.

## Post-demo

Always run **Reset Demo State** to remove the Crusty tenant. Then re-run any setup-project-XX.py scripts for projects whose processes were modified during the demo.
