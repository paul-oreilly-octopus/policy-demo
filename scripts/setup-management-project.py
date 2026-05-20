#!/usr/bin/env python3
"""Management project — hosts runbooks for the demo (mock releases, reset state,
Acquire Crusty Croissant). Lives in the Admin project group, untenanted, uses
the Default Lifecycle (runbooks bypass lifecycles anyway).

This script just creates the project shell. Runbook bodies are added by:
    - setup-runbooks.py            (base: Create Demo Releases, Reset Demo State)
    - setup-acquisition-runbook.py (M5: Acquire Crusty Croissant)
    - setup-refresh-freeze-runbook.py (M1: Refresh Demo Freeze, if fallback path)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

PROJECT_NAME = "Management"
PROJECT_DESCRIPTION = (
    "Operational hub for the Policy Demo. Hosts runbooks for mock releases, "
    "demo state reset, and the live Crusty Croissant acquisition story. "
    "Has no deployment process — runbooks only."
)


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    admin_group_id = foundation["project_groups"]["Admin"]

    # Default Lifecycle is created automatically on space creation
    default_lc = o.find_by_name("/lifecycles", "Default Lifecycle")
    if not default_lc:
        o.err("Default Lifecycle missing — space init incomplete")
        sys.exit(1)

    existing = o.find_by_name("/projects", PROJECT_NAME)
    if existing:
        o.ok(f"project exists: {PROJECT_NAME} ({existing['Id']})")
        project = existing
    else:
        body = {
            "Name": PROJECT_NAME,
            "Description": PROJECT_DESCRIPTION,
            "ProjectGroupId": admin_group_id,
            "LifecycleId": default_lc["Id"],
            "IsDisabled": False,
            "AutoCreateRelease": False,
            "DefaultGuidedFailureMode": "EnvironmentDefault",
            "TenantedDeploymentMode": "Untenanted",
            "DiscreteChannelRelease": False,
        }
        project = o.post("/projects", body)
        o.ok(f"created project: {project['Name']} ({project['Id']})")

    o.save_ids(
        "projects.json",
        {
            "Management": {
                "ProjectId": project["Id"],
                "ProjectSlug": project["Slug"],
            }
        },
    )


if __name__ == "__main__":
    main()
