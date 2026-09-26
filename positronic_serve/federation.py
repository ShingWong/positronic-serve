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

# positronic_serve/federation.py
import json
import logging
import sys
import urllib.request

log = logging.getLogger(__name__)


def rrf_fuse(lists, *, k=8) -> list:
    """Reciprocal-rank fusion across per-source hit lists. Dedup by
    episode_id; each hit tagged with its source_host. A hit present in more
    lists ranks higher (RRF: sum 1/(k_rank + 60) over sources)."""
    import collections
    scores = collections.defaultdict(float)
    source_of = {}
    order = []
    for src in lists:
        for rank, hit in enumerate(src):
            eid = hit.get("episode_id")
            if not eid:
                continue
            scores[eid] += 1.0 / (rank + 60)
            source_of.setdefault(eid, hit)
            if eid not in source_of:
                source_of[eid] = dict(hit)
            if eid not in [o.get("episode_id") for o in order]:
                order.append(hit)
    ranked = sorted(order, key=lambda h: -scores[h.get("episode_id")])
    out = []
    for h in ranked:
        merged = dict(h)
        merged["source_host"] = source_of.get(h.get("episode_id"), {}).get(
            "source_host", "local")
        out.append(merged)
        if len(out) >= k:
            break
    return out


def _call_peer(peer: str, text: str, *, timeout: float, key: str | None) -> list:
    url = peer.rstrip("/") + "/v1/memory/recall"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = json.dumps({"text": text, "k": 8}).encode()
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    j = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    hits = j.get("results", [])
    for h in hits:
        h["source_host"] = peer
    return hits


def federated_recall(cfg: dict, text: str, k: int = 8, *,
                     timeout: float = 3.0) -> dict:
    """Local recall + one-hop peer fan-out. A bad peer is skipped, never fatal."""
    sys.path.insert(0, "/usr/local/devel/positronic/positronic-agent-interface")
    from positronic_ai.ops.recall import run as local_recall

    lists = []
    sources = ["local"]
    try:
        local = local_recall(cfg.get("dir"), text, k=k).get("results", [])
        for h in local:
            h["source_host"] = "local"
        lists.append(local)
    except Exception as e:  # noqa: BLE001
        log.warning("local recall failed: %s", e)

    key = (cfg.get("auth") or {}).get("key") if \
        (cfg.get("auth") or {}).get("manager") == "single" else None
    for peer in cfg.get("peers", []):
        try:
            hits = _call_peer(peer, text, timeout=timeout, key=key)
            if hits:
                lists.append(hits)
                sources.append(peer)
        except Exception as e:  # noqa: BLE001  (peer skip — never fail recall)
            log.warning("peer %s skipped: %s", peer, e)

    return {"results": rrf_fuse(lists, k=k), "sources": sources}