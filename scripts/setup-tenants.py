#!/usr/bin/env python3
"""Tenants: 4 native MMI markets with Region + Acquisition tags applied.

Crusty-Croissant-DE-Berlin is NOT created here — it's created live during the
M5 demo via the 'Acquire Crusty Croissant' runbook (which lives on the
Management project, set up in setup-runbooks.py).

Project connections aren't made here either; they happen as projects are
created in M1-M7 (each project's setup script connects relevant tenants).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

TENANTS = [
    {
        "Name": "MMI-NZ-Auckland",
        "Description": "Muffin Man Inc — New Zealand (Auckland). Native founding market.",
        "Tags": [("Region", "APAC"), ("Acquisition", "native")],
    },
    {
        "Name": "MMI-AU-Sydney",
        "Description": "Muffin Man Inc — Australia (Sydney). Native market.",
        "Tags": [("Region", "APAC"), ("Acquisition", "native")],
    },
    {
        "Name": "MMI-UK-London",
        "Description": "Muffin Man Inc — United Kingdom (London). Native EMEA market.",
        "Tags": [("Region", "EMEA"), ("Acquisition", "native")],
    },
    {
        "Name": "MMI-US-NewYork",
        "Description": "Muffin Man Inc — USA (New York). Native market.",
        "Tags": [("Region", "AMER"), ("Acquisition", "native")],
    },
]


def canonical_tag(foundation: dict, tag_set: str, tag: str) -> str:
    """Return the canonical 'TagSet/Tag' name used by Octopus tag references."""
    return foundation["tag_sets"][tag_set]["Tags"][tag]


def ensure_tenant(t_def: dict, foundation: dict) -> dict:
    existing = o.find_by_name("/tenants", t_def["Name"])
    canonical_tags = [canonical_tag(foundation, ts, tag) for ts, tag in t_def["Tags"]]

    if existing:
        # Merge tags additively
        current = set(existing.get("TenantTags", []))
        desired = set(canonical_tags)
        merged = sorted(current | desired)
        if merged != sorted(current):
            existing["TenantTags"] = merged
            updated = o.put(f"/tenants/{existing['Id']}", existing)
            o.ok(f"tenant updated: {t_def['Name']} ({existing['Id']}) — tags now {merged}")
            return updated
        o.ok(f"tenant exists: {t_def['Name']} ({existing['Id']})")
        return existing

    body = {
        "Name": t_def["Name"],
        "Description": t_def["Description"],
        "TenantTags": canonical_tags,
        "ProjectEnvironments": {},
        "ClonedFromTenantId": None,
    }
    created = o.post("/tenants", body)
    o.ok(f"created tenant: {created['Name']} ({created['Id']}) with tags {canonical_tags}")
    return created


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    tenants: dict[str, str] = {}
    for t_def in TENANTS:
        t = ensure_tenant(t_def, foundation)
        tenants[t["Name"]] = t["Id"]
    o.save_ids("tenants.json", {"tenants": tenants})


if __name__ == "__main__":
    main()
