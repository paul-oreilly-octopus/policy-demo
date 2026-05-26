#!/usr/bin/env python3
"""Pipeline 2: payment-gateway project.

Untenanted, Standard Release lifecycle, deploys to corp-payments-backend
in Cloud-Prod. Baseline process is "non-compliant" — a single mock deploy
step with NO approval gate. The fix during demo is to switch the project's
process to consume the `governed-cloud-prod-deploy` hub process template
which enforces a mandatory manual-intervention approval before the deploy.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "payment-gateway"
PROJECT_DESCRIPTION = (
    "Payment gateway backend. Untenanted Cloud-Prod service. Demonstrates "
    "Process Template governance via M2 — baseline process omits the "
    "mandatory approval step; compliance is achieved by switching the "
    "deployment process to consume the governed-cloud-prod-deploy hub "
    "template."
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
        "TenantedDeploymentMode": "Untenanted",
        "DiscreteChannelRelease": False,
    }
    project = o.post("/projects", body)
    o.ok(f"created project: {project['Name']} ({project['Id']})")
    return project


def set_baseline_process(project: dict, foundation: dict) -> None:
    process = o.get(f"/deploymentprocesses/{project['DeploymentProcessId']}")
    cloud_prod = foundation["environments"]["Cloud-Prod"]

    # Server-side prepare step ensures Dev/Test phases aren't empty — the
    # mock deploy step is scoped to Cloud-Prod only, and Octopus refuses
    # to create deployments where the target env has no matching step.
    prepare_script = (
        '$env = $OctopusParameters["Octopus.Environment.Name"]\n'
        '$release = $OctopusParameters["Octopus.Release.Number"]\n'
        'Write-Host "[MOCK BASELINE] Preparing payment-gateway $release for $env"\n'
        'Write-Host "[MOCK BASELINE] !!! NO APPROVAL GATE — non-compliant baseline."\n'
        'Start-Sleep -Seconds 1\n'
    )
    deploy_script = (
        '$target = $OctopusParameters["Octopus.Machine.Name"]\n'
        '$release = $OctopusParameters["Octopus.Release.Number"]\n'
        '$env = $OctopusParameters["Octopus.Environment.Name"]\n'
        'Write-Host "[MOCK] Deploying payment-gateway $release to $target ($env)"\n'
        'Start-Sleep -Seconds 2\n'
        'Write-Host "[MOCK] Deployment complete."\n'
    )
    steps = [
        {
            "Name": "Prepare release",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Prepare release",
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
            }],
        },
        {
            "Name": "Deploy to corp-payments-backend",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {"Octopus.Action.TargetRoles": "corp-backend"},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Deploy to corp-payments-backend",
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
                    "Octopus.Action.Script.ScriptBody": deploy_script,
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
    o.ok("baseline deployment process set (single mock deploy step, no approval)")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    project = ensure_project(foundation)
    set_baseline_process(project, foundation)
    o.save_ids("projects.json", {
        "payment-gateway": {
            "ProjectId": project["Id"],
            "ProjectSlug": project["Slug"],
        }
    })


if __name__ == "__main__":
    main()
