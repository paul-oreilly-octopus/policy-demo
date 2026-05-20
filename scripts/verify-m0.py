#!/usr/bin/env python3
"""Verify the M0 foundation: space, environments, lifecycles, project groups,
tag sets, tenants, targets, Management project.

Returns non-zero if anything is missing or mis-shaped.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

EXPECTED_ENVS = ["Dev", "Test", "Cloud-Prod", "Cloud-Prod-BreakGlass", "Markets"]
EXPECTED_LIFECYCLES = ["Standard Release", "PCI Standard", "PCI BreakGlass"]
EXPECTED_PROJECT_GROUPS = ["Default Project Group", "Admin"]
EXPECTED_TAG_SETS = {
    "Region": {"APAC", "EMEA", "AMER"},
    "Acquisition": {"native", "acquired-crusty"},
}
EXPECTED_TENANTS = [
    ("MMI-NZ-Auckland", {"Region/APAC", "Acquisition/native"}),
    ("MMI-AU-Sydney",   {"Region/APAC", "Acquisition/native"}),
    ("MMI-UK-London",   {"Region/EMEA", "Acquisition/native"}),
    ("MMI-US-NewYork",  {"Region/AMER", "Acquisition/native"}),
]
EXPECTED_TARGETS = {
    "corp-pos-backend":       ({"Cloud-Prod"}, "Untenanted"),
    "corp-payments-backend":  ({"Cloud-Prod"}, "Untenanted"),
    "corp-mobile-api":        ({"Cloud-Prod"}, "Untenanted"),
    "corp-loyalty":           ({"Cloud-Prod"}, "Untenanted"),
    "corp-marketing":         ({"Cloud-Prod"}, "Untenanted"),
    "corp-pci-vault":         ({"Cloud-Prod", "Cloud-Prod-BreakGlass"}, "Untenanted"),
    "store-nz-auckland-01":   ({"Markets"}, "Tenanted"),
    "store-au-sydney-01":     ({"Markets"}, "Tenanted"),
    "store-uk-london-01":     ({"Markets"}, "Tenanted"),
    "store-us-newyork-01":    ({"Markets"}, "Tenanted"),
}
EXPECTED_PROJECTS = ["Management"]


def check_environments() -> int:
    failures = 0
    envs = {e["Name"]: e for e in o.get_all("/environments")}
    for name in EXPECTED_ENVS:
        if name in envs:
            o.ok(f"env: {name} ({envs[name]['Id']})")
        else:
            o.err(f"env MISSING: {name}")
            failures += 1
    return failures


def check_lifecycles() -> int:
    failures = 0
    lifecycles = {l["Name"]: l for l in o.get_all("/lifecycles")}
    for name in EXPECTED_LIFECYCLES:
        if name in lifecycles:
            n_phases = len(lifecycles[name]["Phases"])
            o.ok(f"lifecycle: {name} ({lifecycles[name]['Id']}, {n_phases} phases)")
        else:
            o.err(f"lifecycle MISSING: {name}")
            failures += 1
    return failures


def check_project_groups() -> int:
    failures = 0
    pgs = {pg["Name"]: pg for pg in o.get_all("/projectgroups")}
    for name in EXPECTED_PROJECT_GROUPS:
        if name in pgs:
            o.ok(f"project group: {name} ({pgs[name]['Id']})")
        else:
            o.err(f"project group MISSING: {name}")
            failures += 1
    return failures


def check_tag_sets() -> int:
    failures = 0
    tagsets = {ts["Name"]: ts for ts in o.get_all("/tagsets")}
    for ts_name, expected_tags in EXPECTED_TAG_SETS.items():
        if ts_name not in tagsets:
            o.err(f"tag set MISSING: {ts_name}")
            failures += 1
            continue
        actual = {t["Name"] for t in tagsets[ts_name].get("Tags", [])}
        missing = expected_tags - actual
        if missing:
            o.err(f"tag set {ts_name}: missing tags {missing}")
            failures += 1
        else:
            o.ok(f"tag set: {ts_name} ({tagsets[ts_name]['Id']}) — tags: {sorted(actual)}")
    return failures


def check_tenants() -> int:
    failures = 0
    tenants = {t["Name"]: t for t in o.get_all("/tenants")}
    for name, expected_tags in EXPECTED_TENANTS:
        if name not in tenants:
            o.err(f"tenant MISSING: {name}")
            failures += 1
            continue
        actual_tags = set(tenants[name].get("TenantTags", []))
        if not expected_tags.issubset(actual_tags):
            o.err(f"tenant {name}: missing tags {expected_tags - actual_tags}")
            failures += 1
        else:
            o.ok(f"tenant: {name} ({tenants[name]['Id']}) — tags: {sorted(actual_tags)}")
    return failures


def check_targets() -> int:
    failures = 0
    envs_by_id = {e["Id"]: e["Name"] for e in o.get_all("/environments")}
    targets = {t["Name"]: t for t in o.get_all("/machines")}
    for name, (expected_envs, expected_participation) in EXPECTED_TARGETS.items():
        if name not in targets:
            o.err(f"target MISSING: {name}")
            failures += 1
            continue
        t = targets[name]
        actual_envs = {envs_by_id.get(eid, eid) for eid in t.get("EnvironmentIds", [])}
        actual_p = t.get("TenantedDeploymentParticipation", "?")
        if actual_envs != expected_envs:
            o.err(f"target {name}: envs {actual_envs} != expected {expected_envs}")
            failures += 1
        elif actual_p != expected_participation:
            o.err(f"target {name}: participation {actual_p} != expected {expected_participation}")
            failures += 1
        else:
            o.ok(f"target: {name} ({t['Id']}) envs={sorted(actual_envs)} p={actual_p}")
    return failures


def check_projects() -> int:
    failures = 0
    projects = {p["Name"]: p for p in o.get_all("/projects")}
    for name in EXPECTED_PROJECTS:
        if name in projects:
            o.ok(f"project: {name} ({projects[name]['Id']})")
        else:
            o.err(f"project MISSING: {name}")
            failures += 1
    return failures


def main() -> int:
    o.info(f"Verifying M0 foundation on space {o.space_id()}…")
    print()

    print("─── Environments ───")
    f1 = check_environments()
    print()
    print("─── Lifecycles ───")
    f2 = check_lifecycles()
    print()
    print("─── Project groups ───")
    f3 = check_project_groups()
    print()
    print("─── Tag sets ───")
    f4 = check_tag_sets()
    print()
    print("─── Tenants ───")
    f5 = check_tenants()
    print()
    print("─── Targets ───")
    f6 = check_targets()
    print()
    print("─── Projects ───")
    f7 = check_projects()
    print()

    total_failures = f1 + f2 + f3 + f4 + f5 + f6 + f7
    if total_failures == 0:
        o.ok(f"M0 foundation verified ✓ ({len(EXPECTED_ENVS)} envs, {len(EXPECTED_LIFECYCLES)} lifecycles, "
             f"{len(EXPECTED_TAG_SETS)} tag sets, {len(EXPECTED_TENANTS)} tenants, "
             f"{len(EXPECTED_TARGETS)} targets, {len(EXPECTED_PROJECTS)} projects)")
        return 0
    else:
        o.err(f"M0 verification failed: {total_failures} issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
