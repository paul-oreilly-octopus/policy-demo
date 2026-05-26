#!/usr/bin/env python3
"""Pipeline 1: holiday-promo-blitz project.

Project: tenanted (all 4 native tenants), Standard Release lifecycle.
Process: single mock 'Deploy promo asset' step running on Markets env only,
targeting `store` tag.
Channels: Default only (M1 demo waits out the freeze; break-glass is shown
in M7 where it actually matters).

This project is "compliant by structure" — it's the freeze that blocks it,
not a missing process step. That's the M1 lesson: deployment freezes can
block compliant projects during sensitive windows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "holiday-promo-blitz"
PROJECT_DESCRIPTION = (
    "Holiday promo asset rollout to all store-front targets. Tenanted by "
    "market. Subject to the rolling demo freeze on the Markets environment "
    "(refreshed every 5 minutes via the Refresh Demo Freeze runbook)."
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


def connect_tenants(project_id: str, tenants: dict, foundation: dict) -> None:
    # Connect each tenant to ALL envs in the Standard Release lifecycle.
    # Octopus requires a tenant connection at every phase of the lifecycle for
    # a release to be planable on a fully-tenanted project, even if the
    # deployment process only has steps that run in the final phase. The
    # actual mock 'Deploy promo asset' step is scoped to Markets via
    # action.environments — earlier phases become no-ops, but tenants must
    # still be connected so Octopus can plan the release.
    needed_envs = {
        foundation["environments"]["Dev"],
        foundation["environments"]["Test"],
        foundation["environments"]["Cloud-Prod"],
        foundation["environments"]["Markets"],
    }
    for tenant_name, tenant_id in tenants["tenants"].items():
        tenant = o.get(f"/tenants/{tenant_id}")
        pe = tenant.get("ProjectEnvironments", {})
        current = set(pe.get(project_id, []))
        new_envs = current | needed_envs
        if new_envs != current:
            pe[project_id] = sorted(new_envs)
            tenant["ProjectEnvironments"] = pe
            o.put(f"/tenants/{tenant_id}", tenant)
            o.ok(f"connected tenant {tenant_name} to {PROJECT_NAME} on {sorted(new_envs - current)}")
        else:
            o.ok(f"tenant {tenant_name} already connected to {PROJECT_NAME} (all 4 envs)")


def set_deployment_process(project: dict, foundation: dict) -> None:
    process = o.get(f"/deploymentprocesses/{project['DeploymentProcessId']}")
    markets_env = foundation["environments"]["Markets"]

    # Server-side "prepare" step runs in every phase so Dev/Test/Cloud-Prod
    # have actual work to schedule. Octopus refuses to create a deployment
    # if the chosen env has no matching steps — even on a tenanted project
    # where the actual rollout is store-only.
    prepare_script = (
        '$env = $OctopusParameters["Octopus.Environment.Name"]\n'
        '$tenant = $OctopusParameters["Octopus.Deployment.Tenant.Name"]\n'
        '$version = $OctopusParameters["Octopus.Release.Number"]\n'
        'Write-Host "[MOCK] Preparing promo asset $version for $env ($tenant)"\n'
        'Start-Sleep -Seconds 1\n'
        'Write-Host "[MOCK] Asset bundled and ready for rollout."\n'
    )
    deploy_script = (
        '$store = $OctopusParameters["Octopus.Machine.Name"]\n'
        '$env = $OctopusParameters["Octopus.Environment.Name"]\n'
        '$tenant = $OctopusParameters["Octopus.Deployment.Tenant.Name"]\n'
        '$version = $OctopusParameters["Octopus.Release.Number"]\n'
        'Write-Host "[MOCK] Deploying promo asset $version to $store ($env / $tenant)"\n'
        'Start-Sleep -Seconds 2\n'
        'Write-Host "[MOCK] Promo asset live."\n'
    )

    steps = [
        {
            "Name": "Prepare promo asset",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [
                {
                    "Name": "Prepare promo asset",
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
                        "Octopus.Action.Script.ScriptBody": prepare_script,
                        "Octopus.Action.RunOnServer": "true",
                    },
                    "Packages": [],
                }
            ],
        },
        {
            "Name": "Deploy promo asset",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {"Octopus.Action.TargetRoles": "store"},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [
                {
                    "Name": "Deploy promo asset",
                    "ActionType": "Octopus.Script",
                    "IsRequired": True,
                    "IsDisabled": False,
                    "Environments": [markets_env],
                    "ExcludedEnvironments": [],
                    "Channels": [],
                    "TenantTags": [],
                    "Properties": {
                        "Octopus.Action.Script.ScriptSource": "Inline",
                        "Octopus.Action.Script.Syntax": "PowerShell",
                        "Octopus.Action.Script.ScriptBody": deploy_script,
                        "Octopus.Action.RunOnServer": "false",
                    },
                    "Packages": [],
                }
            ],
        },
    ]

    if process.get("Steps") == steps:
        o.ok("deployment process up to date")
        return
    process["Steps"] = steps
    o.put(f"/deploymentprocesses/{project['DeploymentProcessId']}", process)
    o.ok("deployment process set: single 'Deploy promo asset' step (Markets env, store role)")


def ensure_default_channel(project: dict, foundation: dict) -> dict:
    channels = o.get_all(f"/projects/{project['Id']}/channels")
    default = next((c for c in channels if c.get("Name") == "Default"), None)
    if not default:
        o.err("Default channel missing — Octopus normally creates this automatically")
        sys.exit(1)
    o.ok(f"Default channel present: {default['Id']}")
    return default


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    tenants = o.load_ids("tenants.json")

    project = ensure_project(foundation)
    set_deployment_process(project, foundation)
    ensure_default_channel(project, foundation)
    connect_tenants(project["Id"], tenants, foundation)

    o.save_ids("projects.json", {
        "holiday-promo-blitz": {
            "ProjectId": project["Id"],
            "ProjectSlug": project["Slug"],
        }
    })


if __name__ == "__main__":
    main()
