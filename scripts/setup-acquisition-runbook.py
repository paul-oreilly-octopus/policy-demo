#!/usr/bin/env python3
"""Acquire Crusty Croissant — runbook on the Management project.

Live-demo flow: when the presenter runs this runbook during M5, it
provisions everything needed to demo the acquired-bakery story:

  1. Creates the Crusty-Croissant-DE-Berlin tenant with tags
     Region/EMEA + Acquisition/acquired-crusty
  2. Creates the store-de-berlin-01 cloud-region target (Markets env)
     connected to that tenant, with `store` role
  3. Connects the tenant to crusty-croissant-pos, customer-mobile-app,
     and loyalty-rewards-service so subsequent demo segments can use it

Idempotent — if the tenant/target already exist (from a prior demo run
that wasn't reset), the runbook reports their IDs and exits clean.

Setup script hardcodes resource IDs into the runbook script body. To
re-render after foundation changes, re-run this script.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

RUNBOOK_NAME = "Acquire Crusty Croissant"
RUNBOOK_DESCRIPTION = (
    "Demo runbook: provisions the acquired-bakery tenant + target + "
    "project connections. Run live during the M5 demo segment. Reversed "
    "by the Reset Demo State runbook."
)

TENANT_NAME = "Crusty-Croissant-DE-Berlin"
TARGET_NAME = "store-de-berlin-01"
SPACE_API = "https://taniwha.octopus.app/api"


SCRIPT_TEMPLATE = """\
$ErrorActionPreference = "Stop"
$apiKey = $OctopusParameters["OctopusApiKey"]
$server = $OctopusParameters["Octopus.Web.ServerUri"]
$spaceId = "{space_id}"

$tenantName        = "{tenant_name}"
$targetName        = "{target_name}"
$regionTag         = "Region/EMEA"
$acquisitionTag    = "Acquisition/acquired-crusty"
$marketsEnvId      = "{markets_env_id}"
$projectIds        = @({connected_projects})

# Tenants must be connected to every lifecycle phase env for release
# planning to succeed on a fully-tenanted project. The mock deploy steps
# only run in Markets, but Dev/Test/Cloud-Prod must still be connected.
$allLifecycleEnvIds = @({all_lifecycle_env_ids})

if (-not $apiKey) {{ throw "OctopusApiKey not set on Management project" }}

$h = @{{ "X-Octopus-ApiKey" = $apiKey }}
$base = "$server/api/$spaceId"

function Invoke-Octo($Method, $Path, $Body) {{
    $args = @{{ Uri = "$base$Path"; Headers = $h; Method = $Method }}
    if ($Body) {{ $args.Body = ($Body | ConvertTo-Json -Depth 10 -Compress); $args.ContentType = "application/json" }}
    return Invoke-RestMethod @args
}}

Write-Host "==> Phase 1: ensure tenant '$tenantName'"
$existing = Invoke-Octo GET "/tenants?partialName=$tenantName&skip=0&take=10"
$tenant = $existing.Items | Where-Object Name -eq $tenantName | Select-Object -First 1

if ($tenant) {{
    Write-Host "    Tenant already exists: $($tenant.Id) — reusing"
}} else {{
    $tenantBody = @{{
        Name = $tenantName
        Description = "Acquired bakery (live demo tenant). Region EMEA. Berlin store."
        TenantTags = @($regionTag, $acquisitionTag)
        ProjectEnvironments = @{{}}
        ClonedFromTenantId = $null
    }}
    $tenant = Invoke-Octo POST "/tenants" $tenantBody
    Write-Host "    Created tenant: $($tenant.Id)"
}}

Write-Host ""
Write-Host "==> Phase 2: ensure target '$targetName'"
$existingTargets = Invoke-Octo GET "/machines?partialName=$targetName&skip=0&take=10"
$target = $existingTargets.Items | Where-Object Name -eq $targetName | Select-Object -First 1

if ($target) {{
    Write-Host "    Target already exists: $($target.Id) — reusing"
}} else {{
    $targetBody = @{{
        Name = $targetName
        Status = "Unknown"
        EnvironmentIds = @($marketsEnvId)
        Roles = @("store")
        TenantIds = @($tenant.Id)
        TenantTags = @()
        TenantedDeploymentParticipation = "Tenanted"
        MachinePolicyId = $null
        Thumbprint = $null
        Uri = $null
        IsDisabled = $false
        Endpoint = @{{ CommunicationStyle = "None"; DefaultWorkerPoolId = ""; Container = @{{ Image = $null; FeedId = $null }} }}
        OperatingSystem = "Unknown"
        ShellName = "Unknown"
        ShellVersion = "Unknown"
    }}
    $target = Invoke-Octo POST "/machines" $targetBody
    Write-Host "    Created target: $($target.Id) (envs=Markets, tenant=$($tenant.Id))"
}}

Write-Host ""
Write-Host "==> Phase 3: connect tenant to demo projects (all lifecycle envs)"
foreach ($projId in $projectIds) {{
    $t = Invoke-Octo GET "/tenants/$($tenant.Id)"
    if (-not $t.ProjectEnvironments) {{ $t | Add-Member ProjectEnvironments @{{}} -Force }}
    $current = @()
    if ($t.ProjectEnvironments.$projId) {{ $current = @($t.ProjectEnvironments.$projId) }}
    $desired = @($current + $allLifecycleEnvIds | Select-Object -Unique | Sort-Object)
    $missing = $desired | Where-Object {{ $current -notcontains $_ }}
    if ($missing) {{
        # Rebuild ProjectEnvironments as a hashtable for clean JSON serialisation
        $pe = @{{}}
        $t.ProjectEnvironments.PSObject.Properties | ForEach-Object {{ $pe[$_.Name] = @($_.Value) }}
        $pe[$projId] = $desired
        $t.ProjectEnvironments = $pe
        Invoke-Octo PUT "/tenants/$($tenant.Id)" $t | Out-Null
        Write-Host "    Connected to project $projId on envs: $($missing -join ', ')"
    }} else {{
        Write-Host "    Already connected to project $projId (all envs)"
    }}
}}

Write-Host ""
Write-Host "==> Acquire Crusty Croissant complete."
Write-Host "    Tenant : $($tenant.Id) ($tenantName)"
Write-Host "    Target : $($target.Id) ($targetName)"
Write-Host "    Tags   : Region/EMEA, Acquisition/acquired-crusty"
Write-Host "    Region : EMEA — GDPR enforcement will fire for this tenant's deploys"
"""


def ensure_runbook(mgmt_project: dict, foundation: dict) -> dict:
    dev_env = foundation["environments"]["Dev"]
    runbooks = o.get_all(f"/projects/{mgmt_project['Id']}/runbooks")
    existing = next((r for r in runbooks if r.get("Name") == RUNBOOK_NAME), None)
    if existing:
        if dev_env not in existing.get("Environments", []):
            existing["Environments"] = sorted(set(existing.get("Environments", [])) | {dev_env})
            o.put(f"/runbooks/{existing['Id']}", existing)
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


def set_runbook_process(runbook: dict, script: str) -> None:
    process = o.get(f"/runbookProcesses/{runbook['RunbookProcessId']}")
    desired = [{
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
                "Octopus.Action.Script.ScriptBody": script,
                "Octopus.Action.RunOnServer": "true",
            },
            "Packages": [],
        }],
    }]
    if process.get("Steps") == desired:
        o.ok("runbook process up to date")
        return
    process["Steps"] = desired
    o.put(f"/runbookProcesses/{runbook['RunbookProcessId']}", process)
    o.ok("runbook process updated")


def publish_snapshot(runbook: dict) -> None:
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    created = o.post("/runbookSnapshots?publish=true", {
        "ProjectId": runbook["ProjectId"],
        "RunbookId": runbook["Id"],
        "Name": f"Auto-{stamp}",
        "Notes": "Auto-published by setup-acquisition-runbook.py",
    })
    o.ok(f"published snapshot {created['Id']}")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    projects = o.load_ids("projects.json")

    needed_projects = ["crusty-croissant-pos", "customer-mobile-app", "loyalty-rewards-service"]
    missing = [p for p in needed_projects if p not in projects]
    if missing:
        o.err(f"missing projects: {missing} — run their setup scripts first")
        sys.exit(1)

    project_ids = ", ".join(f'"{projects[p]["ProjectId"]}"' for p in needed_projects)

    # All envs from the Standard Release lifecycle (Dev/Test/Cloud-Prod/Markets)
    # — the runbook connects Crusty to each of these for each project.
    lifecycle_env_ids = [
        foundation["environments"]["Dev"],
        foundation["environments"]["Test"],
        foundation["environments"]["Cloud-Prod"],
        foundation["environments"]["Markets"],
    ]
    all_lifecycle_env_ids = ", ".join(f'"{e}"' for e in lifecycle_env_ids)

    script = SCRIPT_TEMPLATE.format(
        space_id=foundation["SpaceId"],
        tenant_name=TENANT_NAME,
        target_name=TARGET_NAME,
        markets_env_id=foundation["environments"]["Markets"],
        connected_projects=project_ids,
        all_lifecycle_env_ids=all_lifecycle_env_ids,
    )

    mgmt = o.get(f"/projects/{projects['Management']['ProjectId']}")
    runbook = ensure_runbook(mgmt, foundation)
    set_runbook_process(runbook, script)
    publish_snapshot(runbook)


if __name__ == "__main__":
    main()
