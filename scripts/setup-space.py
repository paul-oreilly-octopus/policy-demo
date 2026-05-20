#!/usr/bin/env python3
"""Create the PolicyDemo space on taniwha.octopus.app.

Idempotent: if a space named 'PolicyDemo' already exists, reuse its ID.

The space manager is set to the current API key's user — required by the API
(POST /api/spaces rejects empty SpaceManagersTeamMembers).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

SPACE_NAME = "PolicyDemo"
SPACE_DESCRIPTION = (
    "Muffin Man Inc — Platform Hub policy demo space. "
    "Seven blocked-pipeline scenarios demonstrating governance via "
    "Deployment Freezes and Process Templates. See "
    "~/dev/claude/octopus/policy-demo/CLAUDE.md."
)


def main() -> None:
    o.info(f"Looking for existing space '{SPACE_NAME}'…")
    existing = None
    for s in o.iget("/spaces?take=200").get("Items", []):
        if s.get("Name") == SPACE_NAME:
            existing = s
            break

    if existing:
        o.ok(f"Space '{SPACE_NAME}' already exists: {existing['Id']}")
        space = existing
    else:
        o.info("Resolving current user (for SpaceManagersTeamMembers)…")
        me = o.iget("/users/me")
        user_id = me["Id"]
        o.ok(f"Current user: {me['Username']} ({user_id})")

        o.info(f"Creating space '{SPACE_NAME}'…")
        body = {
            "Name": SPACE_NAME,
            "Description": SPACE_DESCRIPTION,
            "SpaceManagersTeams": [],
            "SpaceManagersTeamMembers": [user_id],
            "IsDefault": False,
            "TaskQueueStopped": False,
        }
        space = o.ipost("/spaces", body)
        o.ok(f"Created space {space['Id']}")

    o.save_ids(
        "foundation-ids.json",
        {
            "SpaceId": space["Id"],
            "SpaceName": space["Name"],
        },
    )


if __name__ == "__main__":
    main()
