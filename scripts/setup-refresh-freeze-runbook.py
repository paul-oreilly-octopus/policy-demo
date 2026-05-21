#!/usr/bin/env python3
"""Refresh Demo Freeze — runbook + scheduled trigger.

The deployment-freeze schema only supports Daily/Weekly/Monthly recurrence
(no sub-hourly cron). To simulate a "5 min frozen, 5 min open, looping"
demo cadence, this runbook rewrites a single named freeze every 10 minutes
on the 0-mark of every 10-min interval. Each run creates/updates the
'holiday-promo-rolling-freeze' to Start=now, End=now+5min, scoped to the
holiday-promo-blitz project on the Markets environment.

Cadence:
    T=0   runbook fires → freeze T=0..T+5  → frozen for 5 min
    T+5   freeze expires naturally          → open for 5 min
    T+10  runbook fires → freeze T+10..T+15 → frozen again
    ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

RUNBOOK_NAME = "Refresh Demo Freeze"
RUNBOOK_DESCRIPTION = (
    "Rewrites the 'holiday-promo-rolling-freeze' deployment freeze every 10 "
    "minutes to a fresh 5-minute window. Simulates a rolling change-freeze "
    "cadence for the M1 holiday demo (native freeze recurrence supports only "
    "Daily granularity in 2026.2)."
)
TRIGGER_NAME = "Refresh Demo Freeze (every 10 min)"
FREEZE_NAME = "holiday-promo-rolling-freeze"

RUNBOOK_SCRIPT = """\
$ErrorActionPreference = "Stop"

$apiKey = $OctopusParameters["OctopusApiKey"]
$server = $OctopusParameters["Octopus.Web.ServerUri"]
$projectId = $OctopusParameters["Demo.HolidayProjectId"]
$envId = $OctopusParameters["Demo.MarketsEnvironmentId"]
$freezeName = "{freeze_name}"

if (-not $apiKey)    {{ throw "OctopusApiKey variable not set on Management project" }}
if (-not $projectId) {{ throw "Demo.HolidayProjectId variable not set" }}
if (-not $envId)     {{ throw "Demo.MarketsEnvironmentId variable not set" }}

$headers = @{{ "X-Octopus-ApiKey" = $apiKey }}

$nowUtc   = (Get-Date).ToUniversalTime()
$startStr = $nowUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
$endStr   = $nowUtc.AddMinutes(5).ToString("yyyy-MM-ddTHH:mm:ssZ")

Write-Host "Refresh window: Start=$startStr End=$endStr"
Write-Host "Scope: project=$projectId env=$envId"

# Lookup existing freeze by exact name
$searchUrl = "$server/api/deploymentfreezes?skip=0&take=100&partialName=$freezeName"
$response = Invoke-RestMethod -Uri $searchUrl -Headers $headers -Method GET
$existing = $null
foreach ($f in $response.DeploymentFreezes) {{
    if ($f.Name -eq $freezeName) {{ $existing = $f; break }}
}}

$payload = @{{
    Name = $freezeName
    Start = $startStr
    End = $endStr
    ProjectEnvironmentScope = @{{ $projectId = @($envId) }}
    TenantProjectEnvironmentScope = @()
    RecurringSchedule = $null
    Description = "Refreshed by Refresh Demo Freeze runbook. 5-min rolling cadence."
}}

if ($existing) {{
    $payload.Id = $existing.Id
    $body = $payload | ConvertTo-Json -Depth 6 -Compress
    $url = "$server/api/deploymentfreezes/$($existing.Id)"
    $result = Invoke-RestMethod -Uri $url -Headers $headers -Method PUT -Body $body -ContentType "application/json"
    Write-Host "Updated freeze $($existing.Id) — freeze active until $endStr"
}} else {{
    $body = $payload | ConvertTo-Json -Depth 6 -Compress
    $url = "$server/api/deploymentfreezes"
    $result = Invoke-RestMethod -Uri $url -Headers $headers -Method POST -Body $body -ContentType "application/json"
    Write-Host "Created freeze $($result.Id) — freeze active until $endStr"
}}
""".format(freeze_name=FREEZE_NAME)


def add_management_variables(foundation: dict, projects: dict) -> None:
    """Set Demo.HolidayProjectId + Demo.MarketsEnvironmentId on Management project."""
    mgmt_id = projects["Management"]["ProjectId"]
    project = o.get(f"/projects/{mgmt_id}")
    var_set_id = project["VariableSetId"]
    var_set = o.get(f"/variables/{var_set_id}")

    desired = {
        "Demo.HolidayProjectId": projects["holiday-promo-blitz"]["ProjectId"],
        "Demo.MarketsEnvironmentId": foundation["environments"]["Markets"],
    }

    by_name = {v.get("Name"): v for v in var_set["Variables"]}
    changed = False
    for name, value in desired.items():
        if name in by_name:
            if by_name[name].get("Value") != value:
                by_name[name]["Value"] = value
                changed = True
                o.info(f"updated {name} = {value}")
        else:
            var_set["Variables"].append({
                "Name": name, "Value": value, "Description": "",
                "Scope": {}, "IsSensitive": False, "Type": "String",
                "IsEditable": True, "Prompt": None,
            })
            changed = True
            o.info(f"added {name} = {value}")

    if changed:
        o.put(f"/variables/{var_set_id}", var_set)
        o.ok("Management variables updated")
    else:
        o.ok("Management variables already set")


def ensure_runbook(mgmt_project: dict, foundation: dict) -> dict:
    dev_env = foundation["environments"]["Dev"]
    runbooks = o.get_all(f"/projects/{mgmt_project['Id']}/runbooks")
    existing = next((r for r in runbooks if r.get("Name") == RUNBOOK_NAME), None)
    if existing:
        # Ensure Dev env is in the allowed environments list (idempotent fix-up)
        if dev_env not in existing.get("Environments", []):
            existing["Environments"] = sorted(set(existing.get("Environments", [])) | {dev_env})
            existing["EnvironmentScope"] = "Specified"
            o.put(f"/runbooks/{existing['Id']}", existing)
            o.ok(f"runbook updated: {RUNBOOK_NAME} — added Dev env")
        else:
            o.ok(f"runbook exists: {RUNBOOK_NAME} ({existing['Id']})")
        return existing

    body = {
        "Name": RUNBOOK_NAME,
        "Description": RUNBOOK_DESCRIPTION,
        "ProjectId": mgmt_project["Id"],
        "RunbookProcessId": None,
        "PublishedRunbookSnapshotId": None,
        "EnvironmentScope": "Specified",
        "Environments": [dev_env],
        "DefaultGuidedFailureMode": "EnvironmentDefault",
        "RunRetentionPolicy": {"QuantityToKeep": 30, "ShouldKeepForever": False},
        "ConnectivityPolicy": {
            "SkipMachineBehavior": "None",
            "TargetRoles": [],
            "AllowDeploymentsToNoTargets": True,
            "ExcludeUnhealthyTargets": False,
        },
    }
    created = o.post("/runbooks", body)
    o.ok(f"created runbook: {created['Name']} ({created['Id']})")
    return created


def set_runbook_process(runbook: dict) -> None:
    process = o.get(f"/runbookProcesses/{runbook['RunbookProcessId']}")

    desired_steps = [{
        "Name": RUNBOOK_NAME,
        "PackageRequirement": "LetOctopusDecide",
        "Properties": {},
        "Condition": "Success",
        "StartTrigger": "StartAfterPrevious",
        "Actions": [{
            "Name": RUNBOOK_NAME,
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
                "Octopus.Action.Script.ScriptBody": RUNBOOK_SCRIPT,
                "Octopus.Action.RunOnServer": "true",
            },
            "Packages": [],
        }],
    }]

    if process.get("Steps") == desired_steps:
        o.ok("runbook process already up to date")
        return
    process["Steps"] = desired_steps
    o.put(f"/runbookProcesses/{runbook['RunbookProcessId']}", process)
    o.ok("runbook process updated")


def ensure_publication(runbook: dict) -> None:
    """Publish the runbook so the scheduled trigger can run it.

    Always creates a fresh snapshot (timestamp-named) and publishes it, so
    re-runs of this script pick up the latest process body.
    """
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_body = {
        "ProjectId": runbook["ProjectId"],
        "RunbookId": runbook["Id"],
        "Name": f"Auto-{stamp}",
        "Notes": "Auto-published by setup-refresh-freeze-runbook.py",
    }
    created = o.post("/runbookSnapshots?publish=true", snapshot_body)
    o.ok(f"published runbook snapshot {created['Id']} ({created['Name']})")


def ensure_trigger(mgmt_project: dict, runbook: dict, foundation: dict) -> None:
    triggers = o.get_all(f"/projects/{mgmt_project['Id']}/triggers")
    existing = next((t for t in triggers if t.get("Name") == TRIGGER_NAME), None)

    # Runbook triggers need at least one TargetEnvironmentId. Dev is fine — the
    # runbook ignores the environment and just hits the freeze API.
    dev_env = foundation["environments"]["Dev"]

    body = {
        "Name": TRIGGER_NAME,
        "Description": "Fires every 10 minutes on the :00, :10, :20, :30, :40, :50 marks (UTC).",
        "ProjectId": mgmt_project["Id"],
        "IsDisabled": False,
        "Action": {
            "ActionType": "RunRunbook",
            "RunbookId": runbook["Id"],
            "EnvironmentIds": [dev_env],
            "TenantIds": [],
            "TenantTags": [],
        },
        "Filter": {
            "FilterType": "CronExpressionSchedule",
            "CronExpression": "*/10 * * * *",
            "Timezone": "UTC",
        },
    }

    if existing:
        body["Id"] = existing["Id"]
        o.put(f"/projecttriggers/{existing['Id']}", body)
        o.ok(f"trigger updated: {TRIGGER_NAME} ({existing['Id']})")
    else:
        created = o.post("/projecttriggers", body)
        o.ok(f"trigger created: {created['Name']} ({created['Id']})")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    projects = o.load_ids("projects.json")

    if "holiday-promo-blitz" not in projects:
        o.err("holiday-promo-blitz project not found — run setup-project-01-holiday.py first")
        sys.exit(1)

    add_management_variables(foundation, projects)

    mgmt = o.get(f"/projects/{projects['Management']['ProjectId']}")
    runbook = ensure_runbook(mgmt, foundation)
    set_runbook_process(runbook)
    ensure_publication(runbook)
    ensure_trigger(mgmt, runbook, foundation)


if __name__ == "__main__":
    main()
