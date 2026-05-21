#!/usr/bin/env python3
"""Pipeline 3: customer-mobile-app project.

Tenanted (4 native tenants connected), Standard Release lifecycle.
Baseline process is non-compliant — single mock deploy step, no scan.
Demo flow: presenter switches the project's process to consume the
`governed-customer-app-deploy` hub template which adds a mandatory
Security Scan step in Test before any further phase runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "customer-mobile-app"
PROJECT_DESCRIPTION = (
    "Customer-facing mobile ordering app. Tenanted by market. Baseline "
    "process omits the mandatory security scan; compliance is achieved by "
    "switching to consume the governed-customer-app-deploy hub template."
)


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
    markets = foundation["environments"]["Markets"]

    script_backend = (
        '$target = $OctopusParameters["Octopus.Machine.Name"]\n'
        '$release = $OctopusParameters["Octopus.Release.Number"]\n'
        'Write-Host "[MOCK BASELINE] Deploying mobile-app backend $release to $target (NO SCAN)"\n'
        'Start-Sleep -Seconds 2\n'
        'Write-Host "[MOCK BASELINE] Backend live."\n'
    )
    script_stores = (
        '$store = $OctopusParameters["Octopus.Machine.Name"]\n'
        '$tenant = $OctopusParameters["Octopus.Deployment.Tenant.Name"]\n'
        '$release = $OctopusParameters["Octopus.Release.Number"]\n'
        'Write-Host "[MOCK BASELINE] Rolling out mobile-app $release to $store ($tenant) (NO SCAN)"\n'
        'Start-Sleep -Seconds 2\n'
        'Write-Host "[MOCK BASELINE] Store rollout complete."\n'
    )

    steps = [
        {
            "Name": "Deploy backend (Cloud-Prod)",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {"Octopus.Action.TargetRoles": "corp-backend"},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Deploy backend (Cloud-Prod)",
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
                    "Octopus.Action.Script.ScriptBody": script_backend,
                    "Octopus.Action.RunOnServer": "false",
                },
                "Packages": [],
            }],
        },
        {
            "Name": "Deploy to stores (Markets)",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {"Octopus.Action.TargetRoles": "store"},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Deploy to stores (Markets)",
                "ActionType": "Octopus.Script",
                "IsRequired": True,
                "IsDisabled": False,
                "Environments": [markets],
                "ExcludedEnvironments": [],
                "Channels": [],
                "TenantTags": [],
                "Properties": {
                    "Octopus.Action.Script.ScriptSource": "Inline",
                    "Octopus.Action.Script.Syntax": "PowerShell",
                    "Octopus.Action.Script.ScriptBody": script_stores,
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
    o.ok("baseline process set (backend + stores, no scan)")


def connect_tenants(project_id: str, tenants: dict, foundation: dict) -> None:
    markets_env = foundation["environments"]["Markets"]
    cloud_prod_env = foundation["environments"]["Cloud-Prod"]
    for tenant_name, tenant_id in tenants["tenants"].items():
        tenant = o.get(f"/tenants/{tenant_id}")
        pe = tenant.get("ProjectEnvironments", {})
        envs_for_project = set(pe.get(project_id, []))
        new_envs = envs_for_project | {markets_env, cloud_prod_env}
        if new_envs != envs_for_project:
            pe[project_id] = sorted(new_envs)
            tenant["ProjectEnvironments"] = pe
            o.put(f"/tenants/{tenant_id}", tenant)
            o.ok(f"connected tenant {tenant_name} to {PROJECT_NAME}")
        else:
            o.ok(f"tenant {tenant_name} already connected")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    tenants = o.load_ids("tenants.json")
    project = ensure_project(foundation)
    set_baseline_process(project, foundation)
    connect_tenants(project["Id"], tenants, foundation)
    o.save_ids("projects.json", {
        "customer-mobile-app": {
            "ProjectId": project["Id"],
            "ProjectSlug": project["Slug"],
        }
    })


if __name__ == "__main__":
    main()
