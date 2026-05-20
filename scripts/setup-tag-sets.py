#!/usr/bin/env python3
"""Tag sets: Region (single-value), Acquisition (multi-value).

Idempotent — re-running adds missing tags but never drops existing ones.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

TAG_SETS = [
    {
        "Name": "Region",
        "Description": "Geographic region tag set. Single-value. Drives GDPR step gating for EU tenants.",
        "SortOrder": 1,
        "Tags": [
            {"Name": "APAC", "Color": "#0F9D58", "Description": "Asia-Pacific region — Muffin Man Inc native markets."},
            {"Name": "EMEA", "Color": "#4285F4", "Description": "Europe / Middle-East / Africa — triggers GDPR data-residency check."},
            {"Name": "AMER", "Color": "#DB4437", "Description": "Americas — Muffin Man Inc native markets."},
        ],
    },
    {
        "Name": "Acquisition",
        "Description": "Whether the tenant is a native MMI market or part of an acquisition. Multi-value for storytelling.",
        "SortOrder": 2,
        "Tags": [
            {"Name": "native",          "Color": "#666666", "Description": "Muffin Man Inc native market."},
            {"Name": "acquired-crusty", "Color": "#F4B400", "Description": "Acquired from Crusty Croissant Co."},
        ],
    },
]


def ensure_tag_set(ts_def: dict) -> dict:
    existing = o.find_by_name("/tagsets", ts_def["Name"])
    if existing:
        # Merge: add any tags from ts_def that aren't already present (additive only).
        existing_tag_names = {t["Name"] for t in existing.get("Tags", [])}
        added = []
        for tag in ts_def["Tags"]:
            if tag["Name"] not in existing_tag_names:
                # Octopus needs CanonicalTagName etc. for new tags within a tagset;
                # the simplest approach is to POST the full updated tagset.
                existing["Tags"].append(tag)
                added.append(tag["Name"])
        if added:
            updated = o.put(f"/tagsets/{existing['Id']}", existing)
            o.ok(f"tag set updated: {ts_def['Name']} — added tags: {', '.join(added)}")
            return updated
        else:
            o.ok(f"tag set exists: {ts_def['Name']} ({existing['Id']})")
            return existing
    created = o.post("/tagsets", ts_def)
    o.ok(f"created tag set: {created['Name']} ({created['Id']})")
    return created


def main() -> None:
    tag_sets: dict[str, dict] = {}
    for ts_def in TAG_SETS:
        ts = ensure_tag_set(ts_def)
        tag_sets[ts["Name"]] = {
            "Id": ts["Id"],
            "Tags": {tag["Name"]: tag["CanonicalTagName"] for tag in ts.get("Tags", [])},
        }
    o.save_ids("foundation-ids.json", {"tag_sets": tag_sets})


if __name__ == "__main__":
    main()
