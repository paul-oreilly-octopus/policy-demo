#!/usr/bin/env python3
"""Demo teams (idempotent). Provisions all demo teams with their scoped roles.

All teams are space-scoped to PolicyDemo. Each team's role definitions are
data-driven via the TEAMS table — re-running this script adds missing
scoped roles but never removes existing ones.

Teams:
- Prod Change Approvers (M2) — responsible team for manual interventions
  on Cloud-Prod via the governed-cloud-prod-deploy process template.
  Role: Project deployer (space-wide).
- Demo Emergency Responders (M1) — break-glass authority for deploy-freeze
  windows. Role: Project deployer (space-wide).
- PCI Change Approvers (M7) — PCI-DSS-trained approvers for break-glass
  deploys to the cardholder-data vault. Role: Project deployer (space-wide).
- Customer Demo Viewers — external customer accounts. Read-only on the
  space + ability to run the demo runbooks on Management. Roles:
    Project viewer (space-wide)
    Environment viewer (space-wide)
    Runbook consumer (scoped to Management project only)

No external SCIM/AAD link. Adding users to teams is done via the Octopus
UI (UserInvite is system-level, not granted to this script's service
account).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

TEAMS: list[dict] = [
    {
        "Name": "Prod Change Approvers",
        "Description": "Cloud-Prod manual-intervention approvers. Members approve "
                       "production deployments routed through governed-cloud-prod-deploy.",
        "Roles": [
            {"role_name": "Project deployer", "scope_type": "space"},
        ],
    },
    {
        "Name": "Demo Emergency Responders",
        "Description": "Authorised to break-glass deploy-freeze windows when "
                       "needed during the M1 demo segment.",
        "Roles": [
            {"role_name": "Project deployer", "scope_type": "space"},
        ],
    },
    {
        "Name": "PCI Change Approvers",
        "Description": "PCI-DSS-trained approvers for break-glass deploys to the "
                       "cardholder-data vault (M7 demo segment).",
        "Roles": [
            {"role_name": "Project deployer", "scope_type": "space"},
        ],
    },
    {
        "Name": "Customer Demo Viewers",
        "Description": "External customer accounts. Read-only across PolicyDemo + "
                       "able to run demo runbooks on the Management project "
                       "(Acquire Crusty Croissant, Reset Demo State, Refresh Demo "
                       "Freeze). Cannot edit any process — cannot exfiltrate "
                       "sensitive variables. Add customer users to this team via "
                       "the Octopus UI; they will see ONLY the PolicyDemo space.",
        "Roles": [
            {"role_name": "Project viewer",     "scope_type": "space"},
            {"role_name": "Environment viewer", "scope_type": "space"},
            {"role_name": "Runbook consumer",   "scope_type": "project", "project_name": "Management"},
        ],
    },
]


def ensure_team(t_def: dict, space_id: str, role_map: dict[str, str], project_map: dict[str, str]) -> dict:
    name = t_def["Name"]
    existing = next((t for t in o.get_all("/teams") if t.get("Name") == name), None)
    if existing:
        # Update description if drifted
        if existing.get("Description") != t_def["Description"]:
            existing["Description"] = t_def["Description"]
            o.put(f"/teams/{existing['Id']}", existing)
            o.ok(f"team description updated: {name}")
        else:
            o.ok(f"team exists: {name} ({existing['Id']})")
        team = existing
    else:
        body = {
            "Name": name,
            "Description": t_def["Description"],
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

    # Grant each requested role
    existing_scoped = o.iget_all(f"/teams/{team['Id']}/scopeduserroles")
    for role_spec in t_def.get("Roles", []):
        role_name = role_spec["role_name"]
        if role_name not in role_map:
            o.err(f"unknown role: {role_name}")
            sys.exit(1)
        role_id = role_map[role_name]

        scope_type = role_spec["scope_type"]
        if scope_type == "space":
            project_ids: list[str] = []
            scope_label = "space"
        elif scope_type == "project":
            proj_name = role_spec["project_name"]
            if proj_name not in project_map:
                o.err(f"unknown project for role-scoping: {proj_name}")
                sys.exit(1)
            project_ids = [project_map[proj_name]]
            scope_label = f"project={proj_name}"
        else:
            o.err(f"unknown scope_type: {scope_type}")
            sys.exit(1)

        # Idempotency: matching role + space + project-set already present?
        already = any(
            sr.get("UserRoleId") == role_id
            and sr.get("SpaceId") == space_id
            and sorted(sr.get("ProjectIds") or []) == sorted(project_ids)
            for sr in existing_scoped
        )
        if already:
            o.ok(f"  {name}: {role_name} on {scope_label} — already granted")
            continue

        body = {
            "UserRoleId": role_id,
            "TeamId": team["Id"],
            "SpaceId": space_id,
            "EnvironmentIds": [],
            "TenantIds": [],
            "ProjectGroupIds": [],
            "ProjectIds": project_ids,
        }
        o.ipost("/scopeduserroles", body)
        o.ok(f"  {name}: granted {role_name} on {scope_label}")

    return team


def main() -> None:
    space = o.space_id()

    # Build role-name → ID map
    role_map = {r["Name"]: r["Id"] for r in o.iget_all("/userroles")}

    # Build project-name → ID map (for project-scoped roles)
    project_map = {p["Name"]: p["Id"] for p in o.get_all("/projects")}

    team_ids = {}
    for t_def in TEAMS:
        team = ensure_team(t_def, space, role_map, project_map)
        team_ids[t_def["Name"]] = team["Id"]

    o.save_ids("teams.json", {"teams": team_ids})


if __name__ == "__main__":
    main()
