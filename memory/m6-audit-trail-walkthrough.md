---
name: m6-audit-trail-walkthrough
description: Closing demo segment — git log + Octopus audit log + notification log walkthrough
type: project
---

# M6 — Audit trail closing segment

3-minute closing segment after the seven pipelines. No infrastructure to set up — this is presenter scripting only.

## The point

After 25 min of "here's how Platform Hub blocks bad deploys" the audience starts wondering: *who decided these rules?* The audit trail is the answer. Every policy + every break-glass override + every notification is provable evidence — captured automatically.

## What to show (in order)

### 1. Git log on the platform hub repo (60 sec)

Terminal alongside the Octopus UI:

```bash
cd ~/dev/claude/octopus/taniwha.platform_hub
git log --oneline --since="this morning" -- .octopus/process-templates/
```

Talking point: "Every policy in this demo was added via a commit. The hub repo IS the audit trail — and it's how the platform team reviews proposed governance before it goes live."

Then show a single commit in detail:

```bash
git show --stat 27d8f05 -- .octopus/process-templates/governed-customer-app-deploy.ocl
```

Point at:
- The author
- The commit message (the *why*)
- The exact lines that changed

Talking point: "If audit asks 'who added the mandatory security scan and when?' — the answer is in `git log`, not a screenshot of an admin UI."

### 2. Octopus audit log (60 sec)

In Octopus UI → Configuration → Audit.

Filter to today. The audience should see:
- Multiple "Deployment failed because of deployment freeze" events from segment 1 (holiday-promo-blitz blocked)
- The break-glass override from segment 7 (pci-card-data-vault released on Break Glass channel) — *fresh, less than 10 minutes old*
- Manual intervention completions (Prod Change Approvers, PCI Change Approvers)
- Project variable changes from setting `cost_centre` for Crusty tenant in segment 4

Talking point: "Same story from Octopus's perspective. Every block, every override, every approval — recorded with who/when/what."

### 3. Notification log (30 sec)

Terminal beside Octopus:

```bash
tail -f /tmp/policy-demo-notifications.log
```

Should show the break-glass notification entries written by the post-deploy step on the PCI vault Break Glass channel.

Talking point: "In production this is a Slack channel that security gets paged on. The platform team doesn't have to remember to log overrides — the process does it automatically."

### 4. Tie it together (30 sec)

"Three audit surfaces. Git for *what the rules are and who wrote them*. Octopus for *what the rules caught*. Slack/log for *who got told about exceptions*. Auditors don't have to take anyone's word for it — they can verify the whole chain themselves."

## Pre-demo checklist

Before the segment, make sure:

- [ ] At least one break-glass deploy happened earlier (segment 7) so there's a recent override entry to point at
- [ ] `/tmp/policy-demo-notifications.log` has at least one entry from a recent break-glass run (run `cat /tmp/policy-demo-notifications.log` first; if empty, fire a break-glass deploy or seed manually)
- [ ] Octopus audit log filter is pre-set to "today" — don't fiddle with date pickers live
- [ ] Terminal panes are pre-sized so `git log` output is readable to the back row
- [ ] You know the SHA of the most demo-friendly commit to `git show` (`50a4d71` — governed-cloud-prod-deploy add is a good one)

## Backup if something goes wrong

If a service breaks live and there's nothing fresh in the audit log:

- Show `git log` and `git show` on the hub repo — that always works (it's static history, no live system needed)
- Talk through what *would* be in the Octopus audit log even if you can't show it (each pipeline you just demoed creates audit entries)

## What this segment is NOT

- It is not a tour of Octopus's full audit feature set (don't list every event type)
- It is not a Slack integration demo (the log file is a stand-in)
- It is not a Git tutorial

Just: "Three places. Same story. Provable." Then end.
