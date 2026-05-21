#!/usr/bin/env python3
"""Reset Demo State — runbook on Management project.

Removes the live-demo state that the Acquire Crusty Croissant runbook
created (tenant + target + project connections). Idempotent — if nothing
to remove, the runbook reports clean and exits.

What this runbook does NOT do:
    - Reset deployment-process changes the presenter made during the demo
      (e.g. switching customer-mobile-app to consume the hub template).
      Re-run the corresponding setup-project-0X.py to restore baselines.
    - Clear in-progress deployments. Octopus will time them out naturally.
    - Delete deployment freezes. The rolling holiday freeze refreshes on
      a 10-min cron. The PCI permanent freeze is intentional state.

Run between demo presentations.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

RUNBOOK_NAME = "Reset Demo State"
RUNBOOK_DESCRIPTION = (
    "Tears down the live-demo state — Crusty Croissant tenant and "
    "Berlin store target. Safe to run between demos. Does NOT undo "
    "deployment-process changes (re-run setup-project-XX.py for those)."
)

SCRIPT_TEMPLATE = """\
$ErrorActionPreference = "Stop"
$apiKey = $OctopusParameters["OctopusApiKey"]
$server = $OctopusParameters["Octopus.Web.ServerUri"]
$spaceId = "{space_id}"

$tenantName = "Crusty-Croissant-DE-Berlin"
$targetName = "store-de-berlin-01"

$h = @{{ "X-Octopus-ApiKey" = $apiKey }}
$base = "$server/api/$spaceId"

function Invoke-Octo($Method, $Path, $Body) {{
    $args = @{{ Uri = "$base$Path"; Headers = $h; Method = $Method }}
    if ($Body) {{ $args.Body = ($Body | ConvertTo-Json -Depth 10 -Compress); $args.ContentType = "application/json" }}
    return Invoke-RestMethod @args
}}

$cleaned = 0

Write-Host "==> Looking for target '$targetName'"
$targets = Invoke-Octo GET "/machines?partialName=$targetName&skip=0&take=10"
$target = $targets.Items | Where-Object Name -eq $targetName | Select-Object -First 1
if ($target) {{
    Invoke-Octo DELETE "/machines/$($target.Id)" | Out-Null
    Write-Host "    Deleted target $($target.Id)"
    $cleaned++
}} else {{
    Write-Host "    (none — already absent)"
}}

Write-Host ""
Write-Host "==> Looking for tenant '$tenantName'"
$tenants = Invoke-Octo GET "/tenants?partialName=$tenantName&skip=0&take=10"
$tenant = $tenants.Items | Where-Object Name -eq $tenantName | Select-Object -First 1
if ($tenant) {{
    # Deleting a tenant: disconnect from projects first by clearing
    # ProjectEnvironments, then DELETE.
    $tenant.ProjectEnvironments = @{{}}
    Invoke-Octo PUT "/tenants/$($tenant.Id)" $tenant | Out-Null
    Invoke-Octo DELETE "/tenants/$($tenant.Id)" | Out-Null
    Write-Host "    Disconnected from projects and deleted tenant $($tenant.Id)"
    $cleaned++
}} else {{
    Write-Host "    (none — already absent)"
}}

Write-Host ""
Write-Host "==> Cleared $cleaned demo artefact(s)."
if ($cleaned -eq 0) {{
    Write-Host "Demo state was already clean."
}}

Write-Host ""
Write-Host "Note: deployment-process changes made during the demo are NOT"
Write-Host "reverted by this runbook. Re-run setup-project-XX.py scripts"
Write-Host "to restore baselines for any project the presenter modified."
"""


def ensure_runbook(mgmt: dict, foundation: dict) -> dict:
    dev_env = foundation["environments"]["Dev"]
    runbooks = o.get_all(f"/projects/{mgmt['Id']}/runbooks")
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
        "ProjectId": mgmt["Id"],
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
        "Notes": "Auto-published by setup-reset-runbook.py",
    })
    o.ok(f"published snapshot {created['Id']}")


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    projects = o.load_ids("projects.json")
    script = SCRIPT_TEMPLATE.format(space_id=foundation["SpaceId"])
    mgmt = o.get(f"/projects/{projects['Management']['ProjectId']}")
    runbook = ensure_runbook(mgmt, foundation)
    set_runbook_process(runbook, script)
    publish_snapshot(runbook)


if __name__ == "__main__":
    main()
