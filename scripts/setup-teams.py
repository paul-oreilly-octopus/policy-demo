#!/usr/bin/env python3
"""Demo teams (idempotent). Adds teams as needed by milestones M1-M7.

Currently provisions:
- Prod Change Approvers (M2) — responsible team for manual interventions
  on Cloud-Prod via the governed-cloud-prod-deploy process template.
- Demo Emergency Responders (M1) — could break-glass the rolling freeze
  on holiday-promo-blitz (M1 demo doesn't actually exercise break-glass
  for the rolling freeze; this team exists for completeness and is shown
  in the team list during the audit-trail segment).
- PCI Change Approvers (M7) — responsible team for the PCI vault
  break-glass channel manual intervention.

All teams are space-scoped to PolicyDemo. The Project deployer role is
granted to each. No external SCIM/AAD link.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

TEAMS = [
    {
        "Name": "Prod Change Approvers",
        "Description": "Cloud-Prod manual-intervention approvers. Members approve "
                       "production deployments routed through governed-cloud-prod-deploy.",
    },
    {
        "Name": "Demo Emergency Responders",
        "Description": "Authorised to break-glass deploy-freeze windows when "
                       "needed during the M1 demo segment.",
    },
    {
        "Name": "PCI Change Approvers",
        "Description": "PCI-DSS-trained approvers for break-glass deploys to the "
                       "cardholder-data vault (M7 demo segment).",
    },
]


def ensure_team(name: str, description: str, space_id: str, project_deployer_role_id: str) -> dict:
    existing = next((t for t in o.get_all("/teams") if t.get("Name") == name), None)
    if existing:
        o.ok(f"team exists: {name} ({existing['Id']})")
        team = existing
    else:
        body = {
            "Name": name,
            "Description": description,
            "MemberUserIds": [],
            "ExternalSecurityGroups": [],
            "SpaceId": space_id,
            "CanBeDeleted": True,
            "CanBeRenamed": True,
            "CanChangeMembers": True,
            "CanChangeRoles": True,
        }
        team = o.post("/teams", body)
        o.ok(f"created team: {name} ({team['Id']})")

    # Grant Project deployer scoped to this space (idempotent)
    scoped = o.iget_all(f"/teams/{team['Id']}/scopeduserroles")
    have_role = any(
        sr.get("UserRoleId") == project_deployer_role_id and sr.get("SpaceId") == space_id
        for sr in scoped
    )
    if not have_role:
        o.ipost("/scopeduserroles", {
            "UserRoleId": project_deployer_role_id,
            "TeamId": team["Id"],
            "SpaceId": space_id,
            "EnvironmentIds": [],
            "TenantIds": [],
            "ProjectGroupIds": [],
            "ProjectIds": [],
        })
        o.ok(f"granted Project deployer to {name}")

    return team


def main() -> None:
    space = o.space_id()
    pd_role = next((r for r in o.iget_all("/userroles") if r.get("Name") == "Project deployer"), None)
    if not pd_role:
        o.err("Project deployer role not found")
        sys.exit(1)

    team_ids = {}
    for t_def in TEAMS:
        team = ensure_team(t_def["Name"], t_def["Description"], space, pd_role["Id"])
        team_ids[t_def["Name"]] = team["Id"]

    o.save_ids("teams.json", {"teams": team_ids})


if __name__ == "__main__":
    main()
