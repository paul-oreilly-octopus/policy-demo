# Policy Demo — Backlog

## Post-M9 ideas

- **Convert to Config-as-Code** — once the demo is stable, putting the 7 projects' OCL into a Git repo strengthens the audit-trail story (the Octopus admin UI changes during the demo would also appear as commits)
- **Slack webhook integration** — currently writes to `/tmp/policy-demo-notifications.log`; wire to a real `#policy-demo` channel for live demos so the audience sees notifications in their natural habitat instead of a terminal tail. Webhook URL would live in `~/dev/claude/secrets/...` and be injected as a sensitive variable on the Management project.
- **Tenant-tag scoping verification (#7 upgrade)** — if Platform Hub freeze policies turn out to support `target_tags` scoping, switch the PCI vault freeze to use the `permanent-break-glass-only` tag directly (composable: any new sensitive target gets the policy by tagging)
- **Recording-quality demo script** — narrated walkthrough video using the dry-run from M9 as the storyboard
- **Add a 2nd "acquired" tenant mid-demo** — show that the Crusty Croissant story isn't a one-off, the pattern scales (e.g., later acquire "Pastry Paradise" as a French tenant)
- **Channel rules vs policies** — currently we use freezes + step requirements. Could also demonstrate channel rule policies (forbidding pre-release tags from going to Prod, etc.)
- **Required lifecycle policy** — block projects from being created with non-approved lifecycles
- **Compliance-buyer variant** — alternate demo script reframed for CISO / GRC audience (lead with audit, end with onboarding)

## Open questions to resolve during M0

- Platform Hub policy OCL schema — does it support `tenant_tag` scoping for required-step-template policies? (M5 design depends on this)
- Does the freeze policy support cron-style recurrence, or do we need the runbook fallback for the rolling freeze?
- Where should the setup-script repo live on Gitea? (`skynet`? `homelab`? new org?)
- PAT location for the existing `taniwha.platform_hub` repo — already exists somewhere or needs creating?

## Won't-do unless asked

- Real application code — every step stays a mock script. Adding real code drags the demo into infrastructure setup and away from the policy story.
- Real cloud targets (real K8s clusters, real AWS) — Cloud Region targets are the right abstraction for this demo.
- A 6th blocked pipeline (alternative to the meta audit-trail segment) — decided #6 is best as a closing walkthrough, not a forced blocked-pipeline scenario.
