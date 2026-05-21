---
name: m9-demo-script
description: 25-30 min presenter script for the Muffin Man Inc Policy Demo
type: project
---

# Policy Demo — presenter script

25-30 minutes. Platform engineering leaders and technical buyers. Lean into Git/OCL workflow, audit trail, composability. **Three-primitive framing: Deployment Freezes + Process Templates + Policies (Rego/OPA)**.

Key insight to land: **process templates make compliance easy; policies make compliance required**. A policy proves the rule. A template provides the recipe. Belt and braces. The policy is the audit-grade artefact; the template is the developer-experience artefact.

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

> "Octopus Platform Hub gives platform teams **three governance primitives**: deployment freezes, process templates, and Rego-based policies. Today we're going to look at how Muffin Man Inc — a global fast-food chain — uses these three to enforce *seven different things*. Plus a live acquisition story. Plus the audit trail at the end."

> "The relationship to keep in mind: **policies are the rules; templates are the easy path to comply with them**. A project can comply by consuming the hub template OR by adding the right step inline — the policy doesn't care how, only that it's there."

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

**Pipeline:** `payment-gateway` — exercises **Policy + Template**

1. Open the project. Show the deployment process — one step, "Deploy to corp-payments-backend". *"Deploys cardholder-adjacent code. No approval."*
2. **Show the Policy first.** Platform Hub → Policies → `manual-approval-for-prod-deploy`. Walk through the Rego briefly: scope (`Project.Slug == "payment-gateway"` AND `Environment.Name == "Cloud-Prod"`), conditions (require an `Octopus.Manual` step that isn't being skipped). *"This is the rule. Git-tracked, peer-reviewable, auditable. The audit team can see exactly what's enforced and why."*
3. Create Release v1.0.demo. Deploys through Dev → Test → at Cloud-Prod the policy fires (warn or block, depending on `violation_action`). *"That's the rule catching the gap. Auditor would have words."*
4. *"Now: there are two ways to comply. We can add an inline step, OR consume the hub template. Let me show the template path — it's what most teams pick."*
5. Open `.octopus/process-templates/governed-cloud-prod-deploy.ocl` in the Platform Hub repo. Walk through: manual intervention step, deploy step.
6. Back in Octopus: edit payment-gateway → consume `governed-cloud-prod-deploy` template. Parameters: target_role=corp-backend, approver_team_ids=Teams-82 (Prod Change Approvers). Save.
7. Create release v1.0.demo2. At Cloud-Prod: **pauses at the manual intervention** (now satisfies the policy). Show the pause.
8. Approve as a Prod Change Approvers member. Deploy completes. Policy is green.

## Segment 3 — Mandatory security scan (4 min)

**Pipeline:** `customer-mobile-app` — exercises **Policy + Template**

1. Open the project. Baseline: backend deploy + store rollout, no scan.
2. Show the Policy: `mandatory-security-scan` in Platform Hub → Policies. Scope: `customer-mobile-app` at Test. Conditions: a step with name containing "Security Scan" must exist and not be skipped.
3. Create release → at Test, **policy fires** (no Security Scan step in the process).
4. *"Same fix pattern. Consume the hub template — `governed-customer-app-deploy` — which provides the scan step as part of a safe deployment recipe."*
5. Open `governed-customer-app-deploy.ocl` briefly. Show scan + backend + store steps.
6. Edit customer-mobile-app → consume the template. Parameters: backend_target_role=corp-backend, store_target_role=store.
7. New release → Security Scan step fires in Test (logs mocked findings: 0 critical, 0 high, 2 medium…). Policy passes. Deployment proceeds. Audit-quality.

## Segment 4 — Acquire Crusty Croissant (5 min)

**The headline reveal.** Exercises **Policy** (tenant-tag-scoped) + Template.

1. *"Stepping out for a moment. Muffin Man Inc just announced they're acquiring Crusty Croissant Co, a German bakery chain. Integration starts today."*
2. Management project → Runbooks → **Acquire Crusty Croissant**. Run it. ~30 seconds.
3. *"New tenant created with `Region/EMEA` + `Acquisition/acquired-crusty` tags. Berlin store target created. Tenant connected to three projects."*
4. Show the new tenant + its tags in Octopus.
5. *"Now here's the magic. We have a policy already in place — let me show it first."* Platform Hub → Policies → `gdpr-step-for-emea-tenants`. Read the scope: *"this fires when Project.Slug is crusty-croissant-pos AND the tenant has the Region/EMEA tag."* We didn't write this policy *because* of the acquisition. The acquisition fell into a policy that's been live all along.
6. Open `crusty-croissant-pos`. Create release. Deploy to **Crusty-Croissant-DE-Berlin**.
7. **Policy fires** — the baseline process has no GDPR step.
8. Open `eu-region-deploy.ocl` in the hub repo. Show: GDPR data-residency check step (gates on `gdpr_data_residency_region` variable + EU-zone allow-list) + per-tenant store rollout.
9. Edit `crusty-croissant-pos` → consume `eu-region-deploy` template.
10. New release. Deploy to Berlin tenant. **Now fails at the GDPR step itself** with *"GDPR enforcement: deployments serving EMEA tenants must declare 'gdpr_data_residency_region'…"*
11. Add `gdpr_data_residency_region = EU-CENTRAL-1` as a project variable.
12. Re-deploy. Ships clean with GDPR validated. *"The acquisition didn't trigger a special process — it just lit up a tenant-tag-scoped policy that the platform team published years ago. That's the power. New region? New tag? Existing policy applies automatically."*

## Segment 5 — FinOps enforcement on the new tenant (3 min)

**Pipeline:** `loyalty-rewards-service` — exercises **Policy** (variable-aware)

1. *"Same Crusty tenant. Different pipeline. Watch what happens."*
2. Briefly show the policy: `required-finops-variables` in Platform Hub → Policies. Read the Rego: requires `input.Variables.cost_centre` and `input.Variables.owner_email` to be non-empty. *"This policy reads resolved project variables. Native tenants have these set; Crusty doesn't."*
3. Open `loyalty-rewards-service`. Create release. Deploy to Crusty-Croissant-DE-Berlin.
4. **Policy fires.** *"The variables resolve to empty for this tenant. Policy: deny. Reason quoted directly from the Rego."*
5. *"The platform team set FinOps tagging as mandatory ages ago. The new acquired tenant inherits the **requirement**, not the values."*
6. Project Variables. Add `cost_centre = RETAIL-EU-CRUSTY-001` and `owner_email = crusty-finops@muffinman.co`, both scoped to Crusty tenant.
7. Re-deploy. Policy passes. Ships. *"Two minutes of setup, full FinOps lineage going forward."*

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

1. `git log --oneline --since="this morning" -- .octopus/policies/ .octopus/process-templates/` on `taniwha.platform_hub` — today's governance commits, policies and templates side by side
2. `git show bf2ca34` — drill into the commit that added the M2-M5 policies. Point at the Rego scope blocks: *"This is the audit-grade artefact. Git tells you exactly when this rule went live, who reviewed it, and what changed."*
3. Octopus → Configuration → Audit, filter to today — show fresh break-glass deployment from segment 6
4. Highlight the ##NOTIFICATION## line in the task log from earlier
5. *"Four audit surfaces. **Git for what the rules say and who wrote them**. **Octopus audit log for what the rules caught**. **Slack/log for who got told about exceptions**. And the policy evaluation events themselves — every deployment carries a record of every policy it passed (or didn't). Auditors verify the chain end to end. They don't take anyone's word for it."*

## Close (30 sec)

> "Three primitives — deployment freezes, process templates, and Rego policies. Seven different kinds of governance enforced. One tenant onboarded live. One break-glass override executed. Full audit trail at the end. That's Platform Hub."

> "Templates make compliance easy. Policies make compliance required. Freezes block the dangerous windows. Git proves it. That's the model."

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
