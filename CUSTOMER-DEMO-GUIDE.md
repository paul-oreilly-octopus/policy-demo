# Policy Demo — Self-Guided Tour

Welcome. This guide walks you through the **Muffin Man Inc** demo space at your own pace, so you can see Octopus Platform Hub's governance features in action and try them against your own scenarios.

The demo is themed around a fictional global QSR chain — Muffin Man Inc — that has just acquired a German bakery, **Crusty Croissant Co**. Across seven scenarios you'll see how a platform team uses three governance primitives to keep deployments safe, compliant, and auditable, *without* slowing development teams down.

## Before you start

**You'll need:**

- An account on `taniwha.octopus.app` with `Customer Demo Viewers` role — gives you read-only access to the PolicyDemo space + ability to run a few demo-helper runbooks
- *Optional, for hands-on experimentation:* `Project lead` or `Project deployer` role — lets you create releases, deploy, and edit deployment processes yourself. Ask your contact at Octopus to grant this if you want to go beyond observation. Without it you can still walk every scenario and watch existing releases play out — you just can't kick off new ones yourself.
- *Optional, but recommended:* Read access to the `taniwha.platform_hub` GitHub repo — this is where every policy and template lives as a versioned file. You'll see the same OCL files Octopus reads.

**The three governance primitives:**

| Primitive | What it does |
|---|---|
| **Deployment Freezes** | Time-based or permanent blocks on deployments. Scope by project, environment, or tenant. |
| **Process Templates** | Shared, reusable deployment processes. Consuming projects inherit the steps — including governance steps like approvals and security scans. *Templates make compliance easy.* |
| **Policies** | Rego (Open Policy Agent) rules that evaluate every deployment. Returns `allowed: true/false`. Stored as OCL files in the hub repo. *Policies make compliance required.* |

The combination is what gives Platform Hub its power. Templates give engineers a clean recipe; policies prove to auditors the recipe was followed. Below, each scenario shows both at work.

## Time budget

- Skim everything: **~15 minutes**
- One walk-through, observation mode: **~30 minutes**
- Full hands-on with experimentation: **~60-90 minutes**

You can stop after any scenario and come back later.

## The seven scenarios

| # | Scenario | What it demonstrates |
|---|---|---|
| 1 | Rolling holiday freeze | Time-windowed deployment freezes |
| 2 | Mandatory approval before production | Required steps enforced via Policy + Template |
| 3 | Mandatory security scan | Same pattern, applied to a customer-facing app |
| 4 | Required FinOps tagging | Policies that read project variables |
| 5 | Acquisition story (live tenant onboarding) | Tenant-tag-scoped policies that fire automatically when a new region is onboarded |
| 6 | Permanent freeze + break-glass | Channel-routed environments as an exemption mechanism |
| 7 | Audit trail closing review | Git + Octopus audit log + notification log as three audit surfaces |

---

# Scenario 1 — Rolling holiday freeze

**Pipeline:** `holiday-promo-blitz`

**Governance challenge:** marketing wants to push holiday promo assets to stores worldwide, but the platform team has a change-freeze policy during sensitive windows — Black Friday, EOY, etc.

## What to look at

1. In Octopus → Projects → `holiday-promo-blitz`. Look at the deployment process: it just prepares and rolls out a promo asset to store targets. Nothing complicated. The project itself is fully compliant.
2. In Octopus → Configuration → Deployment Freezes → `holiday-promo-rolling-freeze`. Note the `Start` and `End` times — this freeze refreshes every 10 minutes on a 5-minutes-on / 5-minutes-off cycle so you can see it actually working in real time. In production, you'd configure a single freeze for your actual change-freeze window (e.g. 22 Dec to 3 Jan).
3. In Octopus → Library → Runbooks (under Management project) → `Refresh Demo Freeze`. This runbook is what keeps the freeze cycling. Look at the PowerShell — it just `PUT`s a new Start/End every 10 minutes via the API.

## Try it yourself (with deployer access)

1. Pick a moment when the freeze is currently active (check `End` time isn't in the past).
2. On `holiday-promo-blitz`, click **Create Release** → version `1.0.try1` → Save.
3. Click **Deploy to Markets** → select any market tenant (e.g. MMI-UK-London).
4. **Expect a block:** *"The environment Markets is frozen by holiday-promo-rolling-freeze."*
5. Wait until the freeze cycles off (or check the next runbook fire), then retry — succeeds.

## What this demonstrates

- Freezes are first-class objects with audit trails — every freeze has a creator, a start, an end, and a scope
- The block is unambiguous and traceable: the error message names the policy that fired
- The freeze doesn't need to be a permanent rule — it's just a window you open and close as needed
- This is the simplest of the three primitives; useful for predictable, calendar-driven governance

---

# Scenario 2 — Mandatory production approval

**Pipeline:** `payment-gateway`

**Governance challenge:** the platform team wants to enforce that every Cloud-Prod deployment of `payment-gateway` (a sensitive financial backend) has a manual approval gate. Auditors need provable evidence that no code reaches production without a human approving it.

## What to look at

1. In Octopus → Platform Hub → Policies → `manual-approval-for-prod-deploy`. Read the OCL. Notice:
   - `violation_action = "warn"` — currently observable but not blocking. Flip to `"block"` to enforce hard.
   - The `scope` block scopes the policy to project `payment-gateway` deploying to `Cloud-Prod`. Other projects + envs are out of scope.
   - The `conditions` block requires at least one `Octopus.Manual` step in the deployment process, and that no such step is being skipped.
2. In Octopus → Platform Hub → Process Templates → `governed-cloud-prod-deploy`. Open it. This is the *easy path to comply* with the above policy: a process template that already contains the required approval step. Projects consume it and inherit the approval gate.
3. In GitHub, browse `paul-oreilly-octopus/taniwha.platform_hub/.octopus/policies/manual_approval_for_prod_deploy.ocl`. The policy you saw in the UI is just this file — Git is the source of truth. `git log` and `git blame` give you full provenance.

## Try it yourself

1. On `payment-gateway`, look at the current deployment process. It's the **non-compliant baseline** — one mock deploy step, no approval gate.
2. Create a release. Watch it ship through Dev → Test → Cloud-Prod with no pause. The policy fires (in warn mode, so the deploy proceeds; in block mode, it would halt).
3. *To switch to the compliant path:* Edit the deployment process → Add step → select **`governed-cloud-prod-deploy`** from the Platform Hub library. Set parameters: `target_role=corp-backend`, `approver_team_ids=Teams-82` (or whichever team ID is `Prod Change Approvers`).
4. Create a new release. At Cloud-Prod, the deployment pauses for approval. Approve as a member of `Prod Change Approvers`. Ships.

## What this demonstrates

- **Policies declare the requirement.** Templates provide the implementation. A project can comply by adopting the template OR by adding an `Octopus.Manual` step directly. The policy doesn't care how — only that the step is there.
- The platform team writes the policy once and gets the same enforcement across every consuming project.
- Audit-grade: the policy file (in Git) is the rule. The Octopus audit log (per-release) shows whether it fired. The approval itself is recorded by user, time, and release.

---

# Scenario 3 — Mandatory security scan

**Pipeline:** `customer-mobile-app`

**Governance challenge:** customer-facing apps must run an SBOM + SAST scan before being promoted to production. The platform team wants this enforced for every customer-facing service.

## What to look at

1. In Octopus → Platform Hub → Policies → `mandatory-security-scan`. The scope is `customer-mobile-app` at `Test`. The condition requires a step whose name contains `"Security Scan"`.
2. In Octopus → Platform Hub → Process Templates → `governed-customer-app-deploy`. This template includes a `Security Scan (SBOM + SAST)` step that runs server-side in Test. Consume it and the policy is satisfied automatically.
3. In `customer-mobile-app`'s current deployment process: the baseline omits the scan. Audit fail.

## Try it yourself

1. Create a release on `customer-mobile-app`. Watch it pass Test with no scan step running. In block mode, the policy would halt this deployment at Test.
2. Switch the project to consume `governed-customer-app-deploy` (Process → Add step → Platform Hub library → set `backend_target_role=corp-backend`, `store_target_role=store`).
3. Re-deploy. In Test, the scan step fires, logs mocked findings, then proceeds. Policy passes.

## What this demonstrates

- Same pattern as Scenario 2 — policy + template — but applied to a different governance concern (security scanning).
- Reusable. Once you've established the policy + template pair, applying it to a new project is a one-config-change exercise for the consuming team.
- The platform team's intent ("everyone must scan") is encoded as code, not enforced through email reminders or PR reviews.

---

# Scenario 4 — FinOps tagging

**Pipeline:** `loyalty-rewards-service`

**Governance challenge:** finance wants every deployment tagged with `cost_centre` and `owner_email` so usage can be attributed properly. Native MMI markets have these set per-tenant. The acquired Crusty Croissant tenant (which appears in Scenario 5) does not.

## What to look at

1. In Octopus → Platform Hub → Policies → `required-finops-variables`. The Rego reads `input.Variables.cost_centre` and `input.Variables.owner_email` and requires both to resolve non-empty.
2. In Octopus → `loyalty-rewards-service` → Variables. Two variables (`cost_centre`, `owner_email`) are defined, each scoped to one of the four native tenants. The Crusty tenant — added in Scenario 5 — will have no values.

## Try it yourself

1. Create a release on `loyalty-rewards-service`. Deploy to **MMI-NZ-Auckland** tenant. Variables resolve, policy passes, deployment succeeds.
2. Run Scenario 5 first (Acquire Crusty Croissant) so the Crusty tenant exists.
3. Deploy the same release to **Crusty-Croissant-DE-Berlin**. The Verify FinOps Variables step fails because both variables are empty for that tenant.
4. Fix: add `cost_centre` and `owner_email` variables to `loyalty-rewards-service`, scoped to the Crusty tenant. Redeploy. Ships.

## What this demonstrates

- Policies can read resolved variables in their evaluation, not just process structure. This is more flexible than "you must include step X" — you can encode requirements about *what's set*.
- The platform team set the requirement once, years ago. New tenants automatically inherit the rule — they don't inherit the *values* (those are per-tenant) but they inherit the *requirement*.
- For your team this means new business units or customer onboardings can't accidentally start deploying without FinOps coverage. The policy catches it.

---

# Scenario 5 — Acquisition story (live)

**Pipeline:** `crusty-croissant-pos` + multiple others, exercised by the **`Acquire Crusty Croissant`** runbook

**Governance challenge:** Muffin Man Inc just acquired Crusty Croissant Co. The new German subsidiary has different regulatory requirements (GDPR). The platform team wants new EU-region tenants to automatically be subject to data-residency checks without requiring per-project configuration.

## What to look at — before the acquisition

1. In Octopus → Platform Hub → Policies → `gdpr-step-for-emea-tenants`. The scope reads:
   ```
   evaluate if {
       input.Project.Slug == "crusty-croissant-pos"
       "Region/EMEA" in input.Tenant.Tags
   }
   ```
   This policy fires only when the deployment is to a tenant tagged `Region/EMEA`. The platform team wrote this policy long before the acquisition.
2. `crusty-croissant-pos` exists, but has no tenants connected yet. It's a project waiting for the new business unit.
3. In Octopus → Platform Hub → Process Templates → `eu-region-deploy`. This includes a GDPR data-residency check that gates on a `gdpr_data_residency_region` variable from an EU-zone allow-list.

## Run the acquisition

1. In Octopus → Management project → Operations → Runbooks → **`Acquire Crusty Croissant`** → Run.
2. Watch the task succeed (~30 seconds). It creates:
   - A new tenant `Crusty-Croissant-DE-Berlin` with tags `Region/EMEA` and `Acquisition/acquired-crusty`
   - A new target `store-de-berlin-01` connected to that tenant
   - Tenant connections to `crusty-croissant-pos`, `customer-mobile-app`, and `loyalty-rewards-service`
3. In Octopus → Tenants → see the new tenant with its tags applied.

## Try the GDPR enforcement

1. Create a release on `crusty-croissant-pos`. Deploy to the **Crusty-Croissant-DE-Berlin** tenant.
2. **The GDPR policy fires** — even though you didn't change anything on the project. The tenant tag `Region/EMEA` is what brought it into scope. (In warn mode the deploy proceeds; in block mode it halts.)
3. To comply: switch `crusty-croissant-pos` to consume the `eu-region-deploy` template, then set a `gdpr_data_residency_region` project variable to something in the EU allow-list (`EU-CENTRAL-1`, `EU-WEST-1`, etc.).
4. Re-deploy. Ships clean.

## What this demonstrates

- **The acquisition didn't trigger a special governance review.** The policy was there all along. The new tenant fell into a rule that was already live, because of how it was tagged.
- Tag-based scoping is enormously valuable for federated organisations: governance scales with size because it's expressed declaratively, not enforced project-by-project.
- The "scopes" in your policies (region, regulatory zone, customer type) become organisational knobs. Add the right tag to a tenant and the right policies apply.

---

# Scenario 6 — Permanent freeze + break-glass

**Pipeline:** `pci-card-data-vault`

**Governance challenge:** the cardholder-data vault must NEVER deploy under normal circumstances. Only under explicit break-glass authorisation, with full audit trail, and only by approved engineers.

## What to look at

1. In Octopus → Configuration → Deployment Freezes → `pci-card-data-vault-permanent-freeze`. Start: 2026-01-01. End: 2099-12-31. Scope: `pci-card-data-vault` project at `Cloud-Prod` env. Permanent by design.
2. In `pci-card-data-vault` → Channels. Two channels:
   - **Default** — uses the `PCI Standard` lifecycle, which terminates at `Cloud-Prod` (frozen → blocked)
   - **Break Glass** — uses the `PCI BreakGlass` lifecycle, which terminates at `Cloud-Prod-BreakGlass`, an environment specifically created so the freeze does NOT apply. This is "channel-routing" — the override is achieved by deploying to a different env, not by exempting from the freeze.
3. In `pci-card-data-vault` → Process. The manual intervention step and the notification step are scoped to Break Glass channel only. Default channel deploys don't pause for these.

## Try it yourself

1. Create a release on the **Default** channel. Try to deploy to Cloud-Prod → blocked by the permanent freeze. Expected.
2. Create a release on the **Break Glass** channel. You'll be prompted for a `pci_change_ticket` variable — enter a value matching `CHG\d{7}` (e.g. `CHG1234567`).
3. The deployment routes to `Cloud-Prod-BreakGlass` instead. Pauses at the manual intervention. Complete it as a member of `PCI Change Approvers`.
4. Deploy proceeds. The notification step writes a structured `##NOTIFICATION##` entry to the task log. In production, this would be a Slack/PagerDuty alert.

## What this demonstrates

- **A permanent freeze can be sidestepped without disabling it.** The override path (Break Glass channel + different env) preserves the freeze for everyone else — and creates a separate, audited path for emergencies.
- **The override is not a backdoor.** It requires:
  - A specific channel (Break Glass)
  - A change-ticket reference (validated by regex)
  - Approval by a specific team (PCI Change Approvers)
  - A notification step that records the event
- **All four constraints are visible in the deployment process.** Anyone with access can see exactly what a break-glass deploy requires.

---

# Scenario 7 — Audit trail review (closing)

**No new pipeline — this ties everything together.**

After running scenarios 1-6, several audit surfaces should have fresh evidence to look at.

## Surface 1: Git history of the hub repo

In a terminal (or in the GitHub web UI):

```bash
git log --oneline --since="this morning" -- .octopus/policies/ .octopus/process-templates/
```

Every policy and template change is a Git commit. Author, timestamp, diff. Pick any one:

```bash
git show <sha> -- .octopus/policies/manual_approval_for_prod_deploy.ocl
```

This is the audit-grade artefact. When compliance asks "who added this rule and when?", `git log` answers definitively — no admin-UI screenshots required.

## Surface 2: Octopus audit log

In Octopus → Configuration → Audit. Filter to "today." You'll see:

- Multiple deployment-blocked events from Scenario 1 (holiday freeze)
- Process changes from Scenarios 2/3/5 (when you switched projects to consume hub templates)
- Variable changes from Scenarios 4 and 5 (per-tenant FinOps + GDPR vars)
- The break-glass deployment from Scenario 6 (with timestamp, user, and channel)
- Manual intervention completions (who approved what)

## Surface 3: Task log notifications

In Octopus → Tasks. Find the most recent break-glass deployment for `pci-card-data-vault`. Open it. Find the `Record break-glass notification` step. The structured log entry contains:

```
##NOTIFICATION## BREAK_GLASS_DEPLOY
  project    = pci-card-data-vault
  release    = ...
  ticket     = CHG1234567
  approver   = <user>
  timestamp  = ...
```

In production this would fire a webhook (Slack, PagerDuty, ServiceNow). For this demo it's just structured log output you can grep.

## What this demonstrates

- **Three audit surfaces, one consistent story.** Git for what the rules are and who wrote them; Octopus for what the rules caught; the notification log for who got told about exceptions.
- **Auditors verify the whole chain themselves.** They don't have to take anyone's word for it.
- **None of this is bolt-on tooling.** It's built into how the platform team and engineers already work — Git for policies, Octopus for deployments, structured logging for exception reporting.

---

# Resetting the demo

When you're done, or before re-running a scenario:

1. Octopus → Management project → Operations → Runbooks → **`Reset Demo State`** → Run.
2. This removes the live-demo state (Crusty Croissant tenant and Berlin store target). The runbook is safe to re-run multiple times.

**What Reset Demo State does NOT do:** revert any deployment-process changes you made (e.g. switching `payment-gateway` to consume the hub template). If you want a clean slate, ask your Octopus contact to re-run the project setup scripts. Or just leave the changes in place — they're harmless, and re-running a scenario over them will demonstrate the "already compliant" path.

# Going further

Things to try after you've walked the demo:

1. **Edit a policy.** Take one of the policies in `.octopus/policies/` and change `violation_action = "warn"` to `"block"`. Push the commit. Re-create a non-compliant deployment and watch Octopus actually halt it.
2. **Write a new policy.** Use the [policy examples](https://octopus.com/docs/platform-hub/policies/examples) page for inspiration. Try the [Rego Playground](https://play.openpolicyagent.org/) to experiment with the language before authoring the OCL.
3. **Scope a policy to your own real organisation's structure.** What would a `cost_centre` policy look like for your tenants? What about a region-scoped GDPR rule? The schema in [Policies → Schema](https://octopus.com/docs/platform-hub/policies/schema) lists every input field your policies can read.
4. **Look at compliance reports.** Octopus → Insights → Compliance — over time, the report builds a picture of which projects pass which policies, which is useful for ongoing governance reviews.

# Reference links

| Resource | Use it for |
|---|---|
| [Platform Hub overview](https://octopus.com/docs/platform-hub) | The 10,000-foot picture |
| [Platform Hub Policies](https://octopus.com/docs/platform-hub/policies) | Policy feature documentation |
| [Policy examples](https://octopus.com/docs/platform-hub/policies/examples) | Worked examples by use case |
| [Policy schema](https://octopus.com/docs/platform-hub/policies/schema) | The Rego `input` object — every field your policies can read |
| [OCL file format](https://octopus.com/docs/projects/version-control/ocl-file-format) | Config-as-Code syntax for `.ocl` files |
| [OPA documentation home](https://www.openpolicyagent.org/docs/) | Open Policy Agent fundamentals |
| [Rego language reference](https://www.openpolicyagent.org/docs/policy-language) | The full Rego language reference |
| [Rego Playground](https://play.openpolicyagent.org/) | Interactive Rego editor for experimentation |

# Questions?

Reach out to your Octopus contact. They can:

- Grant additional roles if you want hands-on access
- Walk you through writing your first policy
- Help shape policies around your actual organisational requirements
