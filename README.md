# Policy Demo

Octopus Deploy demo space showing Platform Hub policies in action. Themed around **Muffin Man Inc**, a fictional global fast-food chain.

## The demo

Seven deployment pipelines, each blocked by a different governance policy. The demo flow for each:

1. Try to deploy → policy blocks with a clear message
2. Open the policy file in the platform hub Git repo to show *why*
3. Fix the issue (add a step / set a variable / use the break-glass channel)
4. Re-run → goes green through Dev → Test → Cloud-Prod → Markets

| # | Pipeline | Policy demonstrated |
|---|---|---|
| 1 | `holiday-promo-blitz` | Rolling deployment freeze (time-windowed governance) |
| 2 | `payment-gateway` | Mandatory production approval step |
| 3 | `customer-mobile-app` | Mandatory security scan |
| 4 | `loyalty-rewards-service` | Required FinOps tagging variables |
| 5 | `crusty-croissant-pos` | Tenant-tag-scoped GDPR step (acquisition story) |
| 6 | *(closing segment)* | Git-backed audit trail walkthrough |
| 7 | `pci-card-data-vault` | Permanent freeze + break-glass override with audit |

The Crusty Croissant tenant is created **live during the demo** — a "we just acquired this German bakery" moment that immediately bounces off the EMEA-region GDPR policy.

## Architecture

- **Octopus instance:** `taniwha.octopus.app`, space `PolicyDemo`
- **Platform Hub:** existing `github.com/paul-oreilly-octopus/taniwha.platform_hub` — policies go into `.octopus/policies/`
- **Mock infrastructure:** Cloud Region targets stand in for stores and corporate backends; deployment steps are scripts that log what they would do
- **Tenants:** 4 markets (NZ, AU, UK, US) at setup time; 1 acquired tenant (Crusty Croissant DE) added live during demo
- **Runbooks:** drive mock release creation, acquisition reveal, and demo-state reset

For the full architecture and implementation plan, see [`M0-policy-demo-PLAN.md`](./M0-policy-demo-PLAN.md) and [`CLAUDE.md`](./CLAUDE.md).

## Audience

Platform engineering leaders and technical buyers evaluating Octopus Platform Hub for governance use cases.

## Status

Planning complete. M0 (foundation) implementation pending.
