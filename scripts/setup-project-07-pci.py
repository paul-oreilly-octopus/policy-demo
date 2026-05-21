#!/usr/bin/env python3
"""Pipeline 7: pci-card-data-vault project + permanent freeze + break-glass.

Permanent freeze on the Cloud-Prod environment for this project blocks
all Default channel deploys. The Break Glass channel routes through the
PCI BreakGlass lifecycle (which terminates at Cloud-Prod-BreakGlass, an
environment NOT subject to the freeze). Channel-scoped steps require a
PCI change ticket variable and a manual intervention by the PCI Change
Approvers team before the deploy step runs.

Idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "pci-card-data-vault"
PROJECT_DESCRIPTION = (
    "PCI cardholder data vault. Untenanted Cloud-Prod service under "
    "permanent deployment freeze on the Cloud-Prod env. Default channel "
    "is unable to deploy at all. Break Glass channel routes through "
    "Cloud-Prod-BreakGlass (not frozen) and requires PCI change ticket "
    "+ manual approval + audit notification."
)

PERMANENT_FREEZE_NAME = "pci-card-data-vault-permanent-freeze"

# Default channel deploy step — used by both channels; channel-scoping is on
# the manual-intervention + notification steps.
DEPLOY_SCRIPT = """\
$target = $OctopusParameters['Octopus.Machine.Name']
$release = $OctopusParameters['Octopus.Release.Number']
$env = $OctopusParameters['Octopus.Environment.Name']
$channel = $OctopusParameters['Octopus.Release.Channel.Name']
Write-Host "[MOCK] Deploying pci-card-data-vault $release to $target ($env / channel=$channel)"
Start-Sleep -Seconds 2
Write-Host "[MOCK] Vault deploy complete. Audit reference: $release/$channel/$(Get-Date -Format o)"
"""

NOTIFICATION_SCRIPT = """\
$release = $OctopusParameters['Octopus.Release.Number']
$ticket  = $OctopusParameters['pci_change_ticket']
$user    = $OctopusParameters['Octopus.Deployment.Manual.ResponsibleUser']
$ts      = (Get-Date).ToString("o")

Write-Host ""
Write-Host "##NOTIFICATION## BREAK_GLASS_DEPLOY"
Write-Host "  project    = pci-card-data-vault"
Write-Host "  release    = $release"
Write-Host "  ticket     = $ticket"
Write-Host "  approver   = $user"
Write-Host "  timestamp  = $ts"
Write-Host ""
Write-Host "(In production, this fires a Slack/PagerDuty notification."
Write-Host " Demo: presenter shows this entry in the audit walkthrough.)"
"""


def ensure_project(foundation: dict) -> dict:
    existing = o.find_by_name("/projects", PROJECT_NAME)
    if existing:
        # Ensure lifecycle is PCI Standard (Default channel's lifecycle)
        if existing.get("LifecycleId") != foundation["lifecycles"]["PCI Standard"]:
            existing["LifecycleId"] = foundation["lifecycles"]["PCI Standard"]
            o.put(f"/projects/{existing['Id']}", existing)
            o.ok(f"project lifecycle updated → PCI Standard")
        o.ok(f"project exists: {PROJECT_NAME} ({existing['Id']})")
        return existing
    body = {
        "Name": PROJECT_NAME,
        "Description": PROJECT_DESCRIPTION,
        "ProjectGroupId": foundation["project_groups"]["Default Project Group"],
        "LifecycleId": foundation["lifecycles"]["PCI Standard"],
        "IsDisabled": False,
        "AutoCreateRelease": False,
        "DefaultGuidedFailureMode": "EnvironmentDefault",
        "TenantedDeploymentMode": "Untenanted",
        "DiscreteChannelRelease": False,
    }
    project = o.post("/projects", body)
    o.ok(f"created project: {project['Name']} ({project['Id']})")
    return project


def ensure_channels(project: dict, foundation: dict) -> dict[str, str]:
    """Return {channel_name: channel_id} for Default + Break Glass."""
    existing = {c["Name"]: c for c in o.get_all(f"/projects/{project['Id']}/channels")}

    desired = {
        "Default": {
            "LifecycleId": foundation["lifecycles"]["PCI Standard"],
            "Description": "Normal-flow channel for the PCI vault. Subject to the permanent freeze on Cloud-Prod.",
            "IsDefault": True,
        },
        "Break Glass": {
            "LifecycleId": foundation["lifecycles"]["PCI BreakGlass"],
            "Description": "Emergency-deploy channel. Routes to Cloud-Prod-BreakGlass env (not frozen). Requires pci_change_ticket + manual approval + notification.",
            "IsDefault": False,
        },
    }

    result: dict[str, str] = {}
    for name, props in desired.items():
        if name in existing:
            ch = existing[name]
            # Update if lifecycle differs
            if ch.get("LifecycleId") != props["LifecycleId"]:
                ch["LifecycleId"] = props["LifecycleId"]
                ch["Description"] = props["Description"]
                ch["IsDefault"] = props["IsDefault"]
                o.put(f"/projects/{project['Id']}/channels/{ch['Id']}", ch)
                o.ok(f"channel updated: {name} ({ch['Id']})")
            else:
                o.ok(f"channel exists: {name} ({ch['Id']})")
            result[name] = ch["Id"]
        else:
            body = {
                "ProjectId": project["Id"],
                "Name": name,
                "Description": props["Description"],
                "LifecycleId": props["LifecycleId"],
                "IsDefault": props["IsDefault"],
                "Rules": [],
                "TenantTags": [],
            }
            ch = o.post(f"/projects/{project['Id']}/channels", body)
            o.ok(f"channel created: {name} ({ch['Id']})")
            result[name] = ch["Id"]
    return result


def set_deployment_process(project: dict, foundation: dict, channels: dict[str, str]) -> None:
    process = o.get(f"/deploymentprocesses/{project['DeploymentProcessId']}")
    cloud_prod = foundation["environments"]["Cloud-Prod"]
    cloud_prod_bg = foundation["environments"]["Cloud-Prod-BreakGlass"]
    pci_team = o.load_ids("teams.json")["teams"]["PCI Change Approvers"]

    steps = [
        # Step 1: Approval (Break Glass channel only)
        {
            "Name": "Approve break-glass deploy",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Approve break-glass deploy",
                "ActionType": "Octopus.Manual",
                "IsRequired": True,
                "IsDisabled": False,
                "Environments": [cloud_prod_bg],
                "ExcludedEnvironments": [],
                "Channels": [channels["Break Glass"]],
                "TenantTags": [],
                "Properties": {
                    "Octopus.Action.Manual.Instructions": (
                        "**PCI break-glass deploy authorisation**\n\n"
                        "This project is under permanent deployment freeze on Cloud-Prod. "
                        "Deployment is being routed through Cloud-Prod-BreakGlass — the "
                        "channel-routed environment that exempts this release from the freeze.\n\n"
                        "Confirm:\n"
                        "- `pci_change_ticket` is set to a valid CHGxxxxxxx reference: **#{pci_change_ticket}**\n"
                        "- Vault content change has been reviewed by the PCI engineering team\n"
                        "- Notification will be recorded in the audit trail"
                    ),
                    "Octopus.Action.Manual.ResponsibleTeamIds": pci_team,
                    "Octopus.Action.RunOnServer": "true",
                },
                "Packages": [],
            }],
        },
        # Step 2: Deploy to vault (both channels — env determines which target)
        {
            "Name": "Deploy to corp-pci-vault",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {"Octopus.Action.TargetRoles": "permanent-break-glass-only"},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Deploy to corp-pci-vault",
                "ActionType": "Octopus.Script",
                "IsRequired": True,
                "IsDisabled": False,
                "Environments": [cloud_prod, cloud_prod_bg],
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
        # Step 3: Notification (Break Glass channel only)
        {
            "Name": "Record break-glass notification",
            "PackageRequirement": "LetOctopusDecide",
            "Properties": {},
            "Condition": "Success",
            "StartTrigger": "StartAfterPrevious",
            "Actions": [{
                "Name": "Record break-glass notification",
                "ActionType": "Octopus.Script",
                "IsRequired": True,
                "IsDisabled": False,
                "Environments": [cloud_prod_bg],
                "ExcludedEnvironments": [],
                "Channels": [channels["Break Glass"]],
                "TenantTags": [],
                "Properties": {
                    "Octopus.Action.Script.ScriptSource": "Inline",
                    "Octopus.Action.Script.Syntax": "PowerShell",
                    "Octopus.Action.Script.ScriptBody": NOTIFICATION_SCRIPT,
                    "Octopus.Action.RunOnServer": "true",
                },
                "Packages": [],
            }],
        },
    ]

    if process.get("Steps") == steps:
        o.ok("deployment process up to date")
        return
    process["Steps"] = steps
    o.put(f"/deploymentprocesses/{project['DeploymentProcessId']}", process)
    o.ok("deployment process set (approve [BG] + deploy + notify [BG])")


def set_pci_ticket_variable(project: dict) -> None:
    """Add a `pci_change_ticket` project variable with a regex prompt."""
    var_set_id = project["VariableSetId"]
    var_set = o.get(f"/variables/{var_set_id}")
    by_name = {v.get("Name"): v for v in var_set["Variables"]}
    desired = {
        "Name": "pci_change_ticket",
        "Value": "",
        "Description": "Change ticket reference for break-glass deploys (format CHG\\d{7}).",
        "Scope": {},
        "IsSensitive": False,
        "Type": "String",
        "IsEditable": True,
        "Prompt": {
            "Required": True,
            "Label": "PCI Change Ticket",
            "Description": "Must match CHG\\d{7} — e.g. CHG1234567.",
            "DisplaySettings": {"Octopus.ControlType": "SingleLineText"},
        },
    }
    if "pci_change_ticket" in by_name:
        by_name["pci_change_ticket"].update(desired)
    else:
        var_set["Variables"].append(desired)
    o.put(f"/variables/{var_set_id}", var_set)
    o.ok("project variable pci_change_ticket set (with prompt-on-release)")


def ensure_permanent_freeze(project_id: str, foundation: dict) -> None:
    cloud_prod = foundation["environments"]["Cloud-Prod"]
    existing_list = o.iget("/deploymentfreezes?skip=0&take=100").get("DeploymentFreezes", [])
    existing = next((f for f in existing_list if f.get("Name") == PERMANENT_FREEZE_NAME), None)

    body = {
        "Name": PERMANENT_FREEZE_NAME,
        "Description": ("Permanent freeze on the PCI cardholder-data vault project's "
                        "Cloud-Prod env. Break Glass channel routes through "
                        "Cloud-Prod-BreakGlass to sidestep this freeze."),
        "Start": "2026-01-01T00:00:00Z",
        "End": "2099-12-31T23:59:59Z",
        "ProjectEnvironmentScope": {project_id: [cloud_prod]},
        "TenantProjectEnvironmentScope": [],
        "RecurringSchedule": None,
        "OwnerId": None,
    }
    if existing:
        body["Id"] = existing["Id"]
        o.iput(f"/deploymentfreezes/{existing['Id']}", body)
        o.ok(f"permanent freeze updated: {existing['Id']}")
    else:
        created = o.ipost("/deploymentfreezes", body)
        o.ok(f"permanent freeze created: {created['Id']} (scope: project={project_id} env={cloud_prod})")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    project = ensure_project(foundation)
    channels = ensure_channels(project, foundation)
    set_deployment_process(project, foundation, channels)
    set_pci_ticket_variable(project)
    ensure_permanent_freeze(project["Id"], foundation)
    o.save_ids("projects.json", {
        "pci-card-data-vault": {
            "ProjectId": project["Id"],
            "ProjectSlug": project["Slug"],
            "Channels": channels,
        }
    })


if __name__ == "__main__":
    main()
