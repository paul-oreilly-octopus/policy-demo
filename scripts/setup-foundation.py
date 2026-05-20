#!/usr/bin/env python3
"""Foundation: environments, lifecycles, project groups for PolicyDemo.

Idempotent — re-running is safe.

Environments (5):
    Dev, Test, Cloud-Prod, Cloud-Prod-BreakGlass, Markets

Lifecycles (3):
    Standard Release        — Dev → Test → Cloud-Prod → Markets   (auto-promote
                              Dev → Test → Cloud-Prod; manual gate at Markets)
    PCI Standard            — Dev → Test → Cloud-Prod             (manual gate
                              at Cloud-Prod)
    PCI BreakGlass          — Dev → Test → Cloud-Prod-BreakGlass  (manual gate
                              at Cloud-Prod-BreakGlass)

Project Groups (2):
    Default Project Group   — (always present, reused)
    Admin                   — for Management project (runbooks, automation)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

ENVIRONMENTS = [
    {"Name": "Dev",                   "SortOrder": 1, "UseGuidedFailure": False},
    {"Name": "Test",                  "SortOrder": 2, "UseGuidedFailure": False},
    {"Name": "Cloud-Prod",            "SortOrder": 3, "UseGuidedFailure": False},
    {"Name": "Cloud-Prod-BreakGlass", "SortOrder": 4, "UseGuidedFailure": False,
     "Description": "Break-glass-only deployment path for pci-card-data-vault. "
                    "Exists so the permanent freeze on Cloud-Prod can be sidestepped "
                    "via channel-routing without the freeze schema needing channel-exemption."},
    {"Name": "Markets",               "SortOrder": 5, "UseGuidedFailure": False,
     "Description": "Per-market deployment environment (tenanted, required)."},
]

PROJECT_GROUPS = [
    {"Name": "Default Project Group", "Description": "Customer-facing demo projects (the 7 pipelines)."},
    {"Name": "Admin",                 "Description": "Operational/admin projects — Management runbooks, mock releases, demo reset."},
]


def ensure_environment(env_def: dict) -> dict:
    existing = o.find_by_name("/environments", env_def["Name"])
    if existing:
        o.ok(f"environment exists: {env_def['Name']} ({existing['Id']})")
        return existing
    body = {"AllowDynamicInfrastructure": False, **env_def}
    created = o.post("/environments", body)
    o.ok(f"created environment: {created['Name']} ({created['Id']})")
    return created


def ensure_project_group(pg_def: dict) -> dict:
    existing = o.find_by_name("/projectgroups", pg_def["Name"])
    if existing:
        o.ok(f"project group exists: {pg_def['Name']} ({existing['Id']})")
        return existing
    created = o.post("/projectgroups", pg_def)
    o.ok(f"created project group: {created['Name']} ({created['Id']})")
    return created


def ensure_lifecycle(name: str, phases: list[dict], description: str = "") -> dict:
    existing = o.find_by_name("/lifecycles", name)
    body = {
        "Name": name,
        "Description": description,
        "Phases": phases,
        "ReleaseRetentionPolicy": {
            "Unit": "Items",
            "QuantityToKeep": 30,
            "ShouldKeepForever": False,
        },
        "TentacleRetentionPolicy": {
            "Unit": "Items",
            "QuantityToKeep": 5,
            "ShouldKeepForever": False,
        },
    }
    if existing:
        body["Id"] = existing["Id"]
        updated = o.put(f"/lifecycles/{existing['Id']}", body)
        o.ok(f"lifecycle updated: {name} ({existing['Id']})")
        return updated
    created = o.post("/lifecycles", body)
    o.ok(f"created lifecycle: {created['Name']} ({created['Id']})")
    return created


def phase(name: str, env_ids: list[str], automatic: bool = True) -> dict:
    return {
        "Name": name,
        "AutomaticDeploymentTargets": env_ids if automatic else [],
        "OptionalDeploymentTargets": [] if automatic else env_ids,
        "MinimumEnvironmentsBeforePromotion": 0,
        "IsOptionalPhase": False,
    }


def main() -> None:
    envs: dict[str, str] = {}
    for env_def in ENVIRONMENTS:
        env = ensure_environment(env_def)
        envs[env["Name"]] = env["Id"]

    pgs: dict[str, str] = {}
    for pg_def in PROJECT_GROUPS:
        pg = ensure_project_group(pg_def)
        pgs[pg["Name"]] = pg["Id"]

    lifecycles: dict[str, str] = {}

    lc = ensure_lifecycle(
        "Standard Release",
        phases=[
            phase("Dev",        [envs["Dev"]],        automatic=True),
            phase("Test",       [envs["Test"]],       automatic=True),
            phase("Cloud-Prod", [envs["Cloud-Prod"]], automatic=True),
            phase("Markets",    [envs["Markets"]],    automatic=False),
        ],
        description="Standard demo lifecycle. Auto-promote Dev → Test → Cloud-Prod; manual gate at Markets.",
    )
    lifecycles["Standard Release"] = lc["Id"]

    lc = ensure_lifecycle(
        "PCI Standard",
        phases=[
            phase("Dev",        [envs["Dev"]],        automatic=True),
            phase("Test",       [envs["Test"]],       automatic=True),
            phase("Cloud-Prod", [envs["Cloud-Prod"]], automatic=False),
        ],
        description="PCI default-channel lifecycle. Manual gate at Cloud-Prod.",
    )
    lifecycles["PCI Standard"] = lc["Id"]

    lc = ensure_lifecycle(
        "PCI BreakGlass",
        phases=[
            phase("Dev",                   [envs["Dev"]],                   automatic=True),
            phase("Test",                  [envs["Test"]],                  automatic=True),
            phase("Cloud-Prod-BreakGlass", [envs["Cloud-Prod-BreakGlass"]], automatic=False),
        ],
        description="PCI break-glass-channel lifecycle. Bypasses the permanent freeze on Cloud-Prod by routing to Cloud-Prod-BreakGlass.",
    )
    lifecycles["PCI BreakGlass"] = lc["Id"]

    o.save_ids(
        "foundation-ids.json",
        {
            "environments": envs,
            "project_groups": pgs,
            "lifecycles": lifecycles,
        },
    )


if __name__ == "__main__":
    main()
