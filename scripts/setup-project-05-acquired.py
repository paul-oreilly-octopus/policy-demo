#!/usr/bin/env python3
"""Pipeline 5: crusty-croissant-pos project.

This project represents the acquired bakery chain's legacy POS system.
It exists at setup time but has NO tenants connected — the
Crusty-Croissant-DE-Berlin tenant is added live during the M5 demo by
the Acquire Crusty Croissant runbook.

Baseline process is "non-compliant" — a single mock deploy step with
NO GDPR data-residency check. Demo fix: switch to consuming the
`eu-region-deploy` hub template, then add the gdpr_data_residency_region
project variable.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "crusty-croissant-pos"
PROJECT_DESCRIPTION = (
    "Acquired bakery POS system. Single-tenant deployment to "
    "Crusty-Croissant-DE-Berlin (added live during M5 demo). Baseline "
    "lacks GDPR data-residency enforcement; compliance comes from "
    "consuming the eu-region-deploy hub template."
)


DEPLOY_SCRIPT = """\
$store = $OctopusParameters['Octopus.Machine.Name']
$tenant = $OctopusParameters['Octopus.Deployment.Tenant.Name']
$release = $OctopusParameters['Octopus.Release.Number']
Write-Host "[MOCK BASELINE] Deploying crusty-croissant-pos $release to $store ($tenant)"
Write-Host "[MOCK BASELINE] !!! NO GDPR DATA-RESIDENCY CHECK — auditor would flag this."
Start-Sleep -Seconds 2
Write-Host "[MOCK BASELINE] Deployment complete."
"""


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
    markets = foundation["environments"]["Markets"]
    steps = [{
        "Name": "Deploy crusty-croissant-pos",
        "PackageRequirement": "LetOctopusDecide",
        "Properties": {"Octopus.Action.TargetRoles": "store"},
        "Condition": "Success",
        "StartTrigger": "StartAfterPrevious",
        "Actions": [{
            "Name": "Deploy crusty-croissant-pos",
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
                "Octopus.Action.Script.ScriptBody": DEPLOY_SCRIPT,
                "Octopus.Action.RunOnServer": "false",
            },
            "Packages": [],
        }],
    }]
    if process.get("Steps") == steps:
        o.ok("baseline process up to date")
        return
    process["Steps"] = steps
    o.put(f"/deploymentprocesses/{project['DeploymentProcessId']}", process)
    o.ok("baseline process set (mock deploy, no GDPR check)")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    project = ensure_project(foundation)
    set_baseline_process(project, foundation)
    o.save_ids("projects.json", {
        "crusty-croissant-pos": {
            "ProjectId": project["Id"],
            "ProjectSlug": project["Slug"],
        }
    })


if __name__ == "__main__":
    main()
