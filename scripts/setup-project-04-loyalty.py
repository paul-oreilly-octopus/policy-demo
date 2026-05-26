#!/usr/bin/env python3
"""Pipeline 4: loyalty-rewards-service.

Tenanted (4 native tenants), Standard Release lifecycle. This project is
the "good citizen" — it consumes (conceptually) the governed-finops-backend
pattern, and has per-tenant cost_centre + owner_email variables set for
all 4 native tenants. The Crusty Croissant tenant — added live during the
M5 demo — has NO values for these variables, so deploys to that tenant
fail at the Verify FinOps Variables step (provided by the hub template).

For setup, the baseline process here mirrors what the template would
produce, with the verify step inline. (In the demo, presenter can swap
to consuming the actual hub template to show the same enforcement is
delivered via Platform Hub.)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "loyalty-rewards-service"
PROJECT_DESCRIPTION = (
    "Loyalty points engine. Tenanted by market. Demonstrates FinOps "
    "tagging enforcement via mandatory cost_centre/owner_email variables. "
    "Native tenants have these set; the acquired Crusty Croissant tenant "
    "(added live in M5) does not — its deploys block at the verify step."
)


VERIFY_SCRIPT = """\
$ErrorActionPreference = "Stop"
$cc    = $OctopusParameters['cost_centre']
$owner = $OctopusParameters['owner_email']
$tenant = $OctopusParameters['Octopus.Deployment.Tenant.Name']
$env    = $OctopusParameters['Octopus.Environment.Name']

Write-Host "==> Verifying FinOps variables for tenant=$tenant env=$env"
Write-Host "    cost_centre = '$cc'"
Write-Host "    owner_email = '$owner'"

$missing = @()
if ([string]::IsNullOrWhiteSpace($cc))    { $missing += 'cost_centre' }
if ([string]::IsNullOrWhiteSpace($owner)) { $missing += 'owner_email' }

if ($missing.Count -gt 0) {
    Write-Error "Policy violation: required FinOps variable(s) not set for tenant '$tenant': $($missing -join ', '). Define these on the project under Variables, scoped to this tenant."
    exit 1
}
Write-Host "FinOps tags resolved. Proceeding."
"""

DEPLOY_SCRIPT = """\
$target = $OctopusParameters['Octopus.Machine.Name']
$project = $OctopusParameters['Octopus.Project.Name']
$release = $OctopusParameters['Octopus.Release.Number']
$cc = $OctopusParameters['cost_centre']
$owner = $OctopusParameters['owner_email']
Write-Host "[MOCK] Deploying $project $release to $target"
Write-Host "[MOCK]   cost_centre=$cc, owner_email=$owner"
Start-Sleep -Seconds 2
Write-Host "[MOCK] Backend live (FinOps tags emitted to billing pipeline)."
"""

# Per-tenant FinOps variable values (only set for the 4 native tenants —
# Crusty Croissant tenant deliberately omitted).
TENANT_FINOPS = {
    "MMI-NZ-Auckland": {"cost_centre": "RETAIL-NZ-001", "owner_email": "retail-nz@muffinman.co"},
    "MMI-AU-Sydney":   {"cost_centre": "RETAIL-AU-001", "owner_email": "retail-au@muffinman.co"},
    "MMI-UK-London":   {"cost_centre": "RETAIL-UK-001", "owner_email": "retail-uk@muffinman.co"},
    "MMI-US-NewYork":  {"cost_centre": "RETAIL-US-001", "owner_email": "retail-us@muffinman.co"},
}


def ensure_project(foundation: dict) -> dict:
    existing = o.find_by_name("/projects", PROJECT_NAME)
    if existing:
        o.ok(f"project exists: {PROJECT_NAME} ({existing['Id']})")
        return existing
    body = {
        "Name": PROJECT_NAME,
        "Description": PROJECT_DESCRIPTION,
        "ProjectGroupId": foundation["project_groups"]["Default Project Group"],
        "LifecycleId": foundation["lifecycles"]["Standard Release"],
        "IsDisabled": False,
        "AutoCreateRelease": False,
        "DefaultGuidedFailureMode": "EnvironmentDefault",
        "TenantedDeploymentMode": "Tenanted",
        "DiscreteChannelRelease": False,
    }
    project = o.post("/projects", body)
    o.ok(f"created project: {project['Name']} ({project['Id']})")
    return project


def set_baseline_process(project: dict, foundation: dict) -> None:
    process = o.get(f"/deploymentprocesses/{project['DeploymentProcessId']}")
    cloud_prod = foundation["environments"]["Cloud-Prod"]

    steps = [
        {
            "Name": "Verify FinOps Variables",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Verify FinOps Variables",
                "ActionType": "Octopus.Script",
                "IsRequired": True,
                "IsDisabled": False,
                "Environments": [],
                "ExcludedEnvironments": [],
                "Channels": [],
                "TenantTags": [],
                "Properties": {
                    "Octopus.Action.Script.ScriptSource": "Inline",
                    "Octopus.Action.Script.Syntax": "PowerShell",
                    "Octopus.Action.Script.ScriptBody": VERIFY_SCRIPT,
                    "Octopus.Action.RunOnServer": "true",
                },
                "Packages": [],
            }],
        },
        {
            "Name": "Deploy loyalty backend",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {"Octopus.Action.TargetRoles": "corp-backend"},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Deploy loyalty backend",
                "ActionType": "Octopus.Script",
                "IsRequired": True,
                "IsDisabled": False,
                "Environments": [cloud_prod],
                "ExcludedEnvironments": [],
                "Channels": [],
                "TenantTags": [],
                "Properties": {
                    "Octopus.Action.Script.ScriptSource": "Inline",
                    "Octopus.Action.Script.Syntax": "PowerShell",
                    "Octopus.Action.Script.ScriptBody": DEPLOY_SCRIPT,
                    "Octopus.Action.RunOnServer": "false",
                },
                "Packages": [],
            }],
        },
    ]
    if process.get("Steps") == steps:
        o.ok("baseline process up to date")
        return
    process["Steps"] = steps
    o.put(f"/deploymentprocesses/{project['DeploymentProcessId']}", process)
    o.ok("process set (verify + backend deploy)")


def connect_tenants(project_id: str, tenants: dict, foundation: dict) -> None:
    # Connect each tenant to ALL envs in the lifecycle. The project's actual
    # backend deploy step only runs in Cloud-Prod, but a fully-tenanted
    # project still needs tenant connections at every lifecycle phase for
    # release planning to succeed.
    needed_envs = {
        foundation["environments"]["Dev"],
        foundation["environments"]["Test"],
        foundation["environments"]["Cloud-Prod"],
        foundation["environments"]["Markets"],
    }
    for tenant_name, tenant_id in tenants["tenants"].items():
        tenant = o.get(f"/tenants/{tenant_id}")
        pe = tenant.get("ProjectEnvironments", {})
        envs_for_project = set(pe.get(project_id, []))
        new_envs = envs_for_project | needed_envs
        if new_envs != envs_for_project:
            pe[project_id] = sorted(new_envs)
            tenant["ProjectEnvironments"] = pe
            o.put(f"/tenants/{tenant_id}", tenant)
            o.ok(f"connected tenant {tenant_name} to {PROJECT_NAME} on {sorted(new_envs - envs_for_project)}")
        else:
            o.ok(f"tenant {tenant_name} already connected to {PROJECT_NAME} (all 4 envs)")


def set_tenant_finops_variables(project_id: str, tenants: dict, foundation: dict) -> None:
    """Set per-tenant `cost_centre` and `owner_email` project variables."""
    cloud_prod = foundation["environments"]["Cloud-Prod"]
    project = o.get(f"/projects/{project_id}")
    var_set_id = project["VariableSetId"]
    var_set = o.get(f"/variables/{var_set_id}")

    # Build a fresh set of variable definitions
    keep = [v for v in var_set["Variables"] if v.get("Name") not in ("cost_centre", "owner_email")]
    new_vars = list(keep)

    for tenant_name, vals in TENANT_FINOPS.items():
        tenant_id = tenants["tenants"][tenant_name]
        for name, value in vals.items():
            new_vars.append({
                "Name": name,
                "Value": value,
                "Description": f"FinOps tag — {tenant_name}",
                "Scope": {
                    "Tenant": [tenant_id],
                    "Environment": [cloud_prod],
                },
                "IsSensitive": False,
                "Type": "String",
                "IsEditable": True,
                "Prompt": None,
            })

    var_set["Variables"] = new_vars
    o.put(f"/variables/{var_set_id}", var_set)
    o.ok(f"set per-tenant FinOps variables for {len(TENANT_FINOPS)} native tenants")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    tenants = o.load_ids("tenants.json")
    project = ensure_project(foundation)
    set_baseline_process(project, foundation)
    connect_tenants(project["Id"], tenants, foundation)
    set_tenant_finops_variables(project["Id"], tenants, foundation)
    o.save_ids("projects.json", {
        "loyalty-rewards-service": {
            "ProjectId": project["Id"],
            "ProjectSlug": project["Slug"],
        }
    })


if __name__ == "__main__":
    main()
