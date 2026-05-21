#!/usr/bin/env python3
"""Service account user + team + API key for runbook automation.

- User:    svc-policy-demo (IsService: true)
- Team:    Policy Demo Service Account (Space manager role on PolicyDemo)
- API key: issued to svc-policy-demo, applied as sensitive variable
           'OctopusApiKey' on the Management project. Value is shown ONCE on
           creation (by the API) and only ever stored encrypted in Octopus —
           NEVER written to disk by this script.

Idempotent — re-running reuses existing user/team. If the user already has an
API key with our purpose marker, the script skips issuing a new one (the
existing variable on Management is presumed valid).

Roles: Space manager (scoped to PolicyDemo space) — broad enough to manage
projects, runbooks, releases, tenants, targets, deployment freezes from within
runbook scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

SERVICE_USER_USERNAME = "svc-policy-demo"
SERVICE_USER_DISPLAY = "Policy Demo Service Account"
SERVICE_USER_EMAIL = "svc-policy-demo@policy-demo.local"
SERVICE_USER_PURPOSE = "policy-demo:runbook-automation"

SERVICE_TEAM_NAME = "Policy Demo Service Account"
SERVICE_TEAM_DESCRIPTION = (
    "Holds the svc-policy-demo service user. Used by runbooks on the "
    "Management project (mock release generation, freeze refresh, "
    "Acquire Crusty Croissant). Role: Space manager scoped to PolicyDemo."
)

MANAGEMENT_VAR_NAME = "OctopusApiKey"


def ensure_service_user() -> dict:
    # Look up user by username (instance-level)
    for u in o.iget_all("/users"):
        if u.get("Username") == SERVICE_USER_USERNAME:
            o.ok(f"service user exists: {u['Username']} ({u['Id']})")
            return u
    body = {
        "Username": SERVICE_USER_USERNAME,
        "DisplayName": SERVICE_USER_DISPLAY,
        "EmailAddress": SERVICE_USER_EMAIL,
        "IsActive": True,
        "IsService": True,
        "Password": None,
    }
    created = o.ipost("/users", body)
    o.ok(f"created service user: {created['Username']} ({created['Id']})")
    return created


def ensure_service_team(user_id: str, space_id: str) -> dict:
    # Look up team by name within space
    teams = o.get_all("/teams")
    existing = next((t for t in teams if t.get("Name") == SERVICE_TEAM_NAME), None)
    if existing:
        # Make sure member + scoped role is present
        members = set(existing.get("MemberUserIds", []))
        if user_id not in members:
            existing["MemberUserIds"] = sorted(members | {user_id})
            o.put(f"/teams/{existing['Id']}", existing)
            o.ok(f"added service user to team: {SERVICE_TEAM_NAME}")
        else:
            o.ok(f"team exists with member: {SERVICE_TEAM_NAME} ({existing['Id']})")
        team = existing
    else:
        body = {
            "Name": SERVICE_TEAM_NAME,
            "Description": SERVICE_TEAM_DESCRIPTION,
            "MemberUserIds": [user_id],
            "ExternalSecurityGroups": [],
            "SpaceId": space_id,
            "CanBeDeleted": True,
            "CanBeRenamed": True,
            "CanChangeMembers": True,
            "CanChangeRoles": True,
        }
        team = o.post("/teams", body)
        o.ok(f"created team: {team['Name']} ({team['Id']})")

    # Ensure Space manager role is granted to the team scoped to this space
    space_manager_role = next(
        (r for r in o.iget_all("/userroles") if r.get("Name") == "Space manager"),
        None,
    )
    if not space_manager_role:
        o.err("Space manager role not found")
        sys.exit(1)

    # Scoped user roles are managed via /scopeduserroles
    scoped_roles = o.iget_all(f"/teams/{team['Id']}/scopeduserroles")
    have_role = any(
        sr.get("UserRoleId") == space_manager_role["Id"] and sr.get("SpaceId") == space_id
        for sr in scoped_roles
    )
    if have_role:
        o.ok(f"team already has Space manager role scoped to {space_id}")
    else:
        body = {
            "UserRoleId": space_manager_role["Id"],
            "TeamId": team["Id"],
            "SpaceId": space_id,
            "EnvironmentIds": [],
            "TenantIds": [],
            "ProjectGroupIds": [],
            "ProjectIds": [],
        }
        o.ipost("/scopeduserroles", body)
        o.ok(f"granted Space manager role to {team['Name']} on {space_id}")

    return team


def ensure_api_key(user: dict) -> str | None:
    """Return the API key value if a NEW one was issued, else None (existing key on file).

    The API key value is returned ONCE only. If we need to set the Management
    variable, the caller must use the returned value within this run.
    """
    keys = o.iget(f"/users/{user['Id']}/apikeys?skip=0&take=200").get("Items", [])
    for k in keys:
        if k.get("Purpose") == SERVICE_USER_PURPOSE:
            o.ok(f"API key exists for {user['Username']} ({k['Id']}, purpose: {SERVICE_USER_PURPOSE})")
            return None  # We can't retrieve the value; presume Management variable is set

    body = {"Purpose": SERVICE_USER_PURPOSE, "Expires": None}
    created = o.ipost(f"/users/{user['Id']}/apikeys", body)
    key_value = created.get("ApiKey")
    if not key_value:
        o.err("API key response missing 'ApiKey' field")
        sys.exit(1)
    o.ok(f"issued new API key for {user['Username']} ({created['Id']})")
    return key_value


def apply_management_variable(api_key_value: str) -> None:
    projects = o.load_ids("projects.json")
    mgmt_id = projects["Management"]["ProjectId"]
    project = o.get(f"/projects/{mgmt_id}")
    var_set_id = project["VariableSetId"]
    var_set = o.get(f"/variables/{var_set_id}")

    # Find existing OctopusApiKey variable or add new one
    found = False
    for var in var_set["Variables"]:
        if var.get("Name") == MANAGEMENT_VAR_NAME:
            var["Value"] = api_key_value
            var["IsSensitive"] = True
            var["Type"] = "Sensitive"
            found = True
            break
    if not found:
        var_set["Variables"].append({
            "Name": MANAGEMENT_VAR_NAME,
            "Value": api_key_value,
            "Description": f"API key for {SERVICE_USER_USERNAME} — runbook automation",
            "Scope": {},
            "IsSensitive": True,
            "Type": "Sensitive",
            "IsEditable": True,
            "Prompt": None,
        })

    o.put(f"/variables/{var_set_id}", var_set)
    o.ok(f"applied API key as sensitive variable '{MANAGEMENT_VAR_NAME}' on Management project")


def main() -> None:
    space = o.space_id()
    user = ensure_service_user()
    team = ensure_service_team(user["Id"], space)
    new_key = ensure_api_key(user)

    if new_key:
        apply_management_variable(new_key)
    else:
        o.info(f"existing API key already on file — Management '{MANAGEMENT_VAR_NAME}' variable assumed in place")

    o.save_ids("service-account.json", {
        "ServiceUserId": user["Id"],
        "ServiceUserUsername": user["Username"],
        "ServiceTeamId": team["Id"],
        "ApiKeyPurpose": SERVICE_USER_PURPOSE,
    })


if __name__ == "__main__":
    main()
