# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

# positronic_serve/audit.py
"""τ-ordered JSONL audit trail for bound-single denials (PEEP-0002 §4.5)."""

import json
import sys
import time
import uuid
from pathlib import Path


def deny_bound_mismatch(cfg: dict, *, origin: str, claims: dict, path: str,
                        key_id: str | None = None,
                        forwarded_for: str | None = None) -> None:
    """Append one metadata-only record to <data_dir>/audit.log.

    Fire-and-forget: a write failure goes to stderr and never raises, so the
    401 response is never delayed or replaced.
    """
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tau": int(time.time()),
        "request_id": uuid.uuid4().hex,
        "key_id": key_id,
        "allowed_subnet": claims.get("allowed_subnet"),
        "allowed_domain": claims.get("allowed_domain"),
        "origin": origin,
        "forwarded_for": forwarded_for,
        "path": path,
        "decision": "deny_bound_mismatch",
        "scheme": "bound-single",
    }
    try:
        log = Path(cfg.get("dir") or ".") / "audit.log"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError as exc:
        print(f"audit: write failed: {exc}", file=sys.stderr)
