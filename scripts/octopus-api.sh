#!/usr/bin/env bash
# Shared bash helper for Octopus Deploy API calls against the PolicyDemo space.
# Source from other scripts: source "$(dirname "$0")/octopus-api.sh"
#
# Security: API key is fed to curl via -H @<(...) process substitution so the
# value never appears in argv (visible to `ps`). Never echo or log it.

set -euo pipefail

OCTOPUS_SERVER="https://taniwha.octopus.app"
OCTOPUS_API_ROOT="${OCTOPUS_SERVER}/api"
OCTOPUS_KEY_FILE="${HOME}/dev/claude/secrets/taniwha.octopus.app/api_key"
POLICY_DEMO_CONFIG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/foundation-ids.json"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${CYAN}→${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }

_octo_header_value() {
  if [[ ! -f "$OCTOPUS_KEY_FILE" ]]; then
    err "API key file not found at $OCTOPUS_KEY_FILE"
    exit 1
  fi
  echo "X-Octopus-ApiKey: $(grep '^value:' "$OCTOPUS_KEY_FILE" | awk '{print $2}')"
}

_octo_curl() {
  curl -s --fail-with-body -H @<(_octo_header_value) "$@"
}

# Resolve the PolicyDemo space ID — from config file if present, else look up by name.
octopus_space_id() {
  if [[ -f "$POLICY_DEMO_CONFIG" ]]; then
    local sid
    sid=$(python3 -c "import sys, json; print(json.load(open(sys.argv[1])).get('SpaceId',''))" "$POLICY_DEMO_CONFIG")
    if [[ -n "$sid" ]]; then echo "$sid"; return; fi
  fi
  _octo_curl "${OCTOPUS_API_ROOT}/spaces?take=200" | \
    python3 -c "import sys, json; [print(s['Id']) for s in json.load(sys.stdin).get('Items',[]) if s.get('Name')=='PolicyDemo']" \
    | head -1
}

# Instance-scoped calls
octopus_iget()    { _octo_curl "${OCTOPUS_API_ROOT}$1"; }
octopus_ipost()   { _octo_curl -H "Content-Type: application/json" -X POST "${OCTOPUS_API_ROOT}$1" --data-binary "$2"; }
octopus_iput()    { _octo_curl -H "Content-Type: application/json" -X PUT  "${OCTOPUS_API_ROOT}$1" --data-binary "$2"; }
octopus_idelete() { _octo_curl -X DELETE "${OCTOPUS_API_ROOT}$1"; }

# Space-scoped calls
octopus_get()    { local sid; sid=$(octopus_space_id); _octo_curl "${OCTOPUS_API_ROOT}/${sid}$1"; }
octopus_post()   { local sid; sid=$(octopus_space_id); _octo_curl -H "Content-Type: application/json" -X POST "${OCTOPUS_API_ROOT}/${sid}$1" --data-binary "$2"; }
octopus_put()    { local sid; sid=$(octopus_space_id); _octo_curl -H "Content-Type: application/json" -X PUT  "${OCTOPUS_API_ROOT}/${sid}$1" --data-binary "$2"; }
octopus_delete() { local sid; sid=$(octopus_space_id); _octo_curl -X DELETE "${OCTOPUS_API_ROOT}/${sid}$1"; }
