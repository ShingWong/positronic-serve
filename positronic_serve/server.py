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

# positronic_serve/server.py
import json

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from positronic_serve.audit import deny_bound_mismatch
from positronic_serve.auth import (
    build_key_manager,
    host_matches_domain,
    ip_in_subnet,
)


async def _body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _auth_ok(request: Request, cfg: dict) -> bool:
    mgr = build_key_manager(cfg.get("auth", {}))
    header = request.headers.get("authorization", "")
    token = header[7:] if header.startswith("Bearer ") else None
    if not mgr.validate(token):
        return False
    claims = mgr.inspect(token)
    if claims is None:                    # local/single carry no claims
        return True
    origin = _origin(request, cfg)
    if not ip_in_subnet(origin, claims.get("allowed_subnet", "")):
        _deny_bound_mismatch(cfg, mgr, claims, origin, request)
        return False
    if not host_matches_domain(request.headers.get("host", ""),
                                claims.get("allowed_domain", "")):
        _deny_bound_mismatch(cfg, mgr, claims, origin, request)
        return False
    return True


def _origin(request: Request, cfg: dict) -> str:
    """Direct peer address, unless a trusted proxy forwarded the request."""
    peer = (request.client.host if request.client else "") or ""
    xff = request.headers.get("x-forwarded-for", "")
    trusted = cfg.get("trusted_proxies") or []
    if not xff or not _trusted(peer, trusted):
        return peer
    hops = [hop.strip() for hop in xff.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _trusted(hop, trusted):
            return hop
    return hops[0] if hops else peer


def _trusted(ip: str, cidrs: list) -> bool:
    return any(ip_in_subnet(ip, cidr) for cidr in cidrs)


def _deny_bound_mismatch(cfg: dict, mgr, claims: dict, origin: str,
                         request: Request) -> None:
    deny_bound_mismatch(
        cfg,
        origin=origin,
        claims=claims,
        path=request.url.path,
        key_id=(mgr.describe() or {}).get("key_id"),
        forwarded_for=request.headers.get("x-forwarded-for") or None,
    )


def create_app(cfg: dict):
    # positronic_ai is a declared dependency (see pyproject.toml), so it is
    # already importable. There used to be a sys.path.insert(0, <checkout>)
    # here, which was redundant *and* harmful: at position 0 it shadowed the
    # installed package with whatever the working tree happened to hold, so a
    # stale or uncommitted tree silently won over a correct install.
    from positronic_ai.ops import ask as _ask
    from positronic_ai.ops import consolidate as _cons
    from positronic_ai.ops import ingest as _ing
    from positronic_ai.ops import prune as _pr
    from positronic_ai.ops import recall as _rc

    pdir = cfg.get("dir")
    brain = cfg.get("brain", "kairos")

    async def healthz(request: Request):
        return JSONResponse({"ok": True, "brain": brain,
                             "peers": len(cfg.get("peers", []))})

    async def recall(request: Request):
        if not _auth_ok(request, cfg):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        b = await _body(request)
        out = _rc.run(pdir, b.get("text", ""), k=b.get("k", 8),
                      consolidation=b.get("consolidation"),
                      context_window=b.get("context_window", 0))
        return JSONResponse(out)

    async def ask(request: Request):
        if not _auth_ok(request, cfg):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        b = await _body(request)
        return JSONResponse(_ask.run(pdir, b.get("object", "")))

    async def consolidate(request: Request):
        if not _auth_ok(request, cfg):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        b = await _body(request)
        return JSONResponse(_cons.run(pdir, b.get("text", ""),
                                      brain=b.get("brain", brain),
                                      arousal=b.get("arousal", 0.4)))

    async def prune(request: Request):
        if not _auth_ok(request, cfg):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse(_pr.run(pdir, brain=brain))

    async def ingest(request: Request):
        if not _auth_ok(request, cfg):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        b = await _body(request)
        return JSONResponse(_ing.run(pdir, b.get("text", ""),
                                     brain=b.get("brain", brain),
                                     arousal=b.get("arousal", 0.5)))

    async def peers(request: Request):
        return JSONResponse({"peers": cfg.get("peers", [])})

    async def federated_recall(request: Request):
        if not _auth_ok(request, cfg):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        b = await _body(request)
        from positronic_serve.federation import federated_recall as _fed
        return JSONResponse(_fed(cfg, b.get("text", ""), k=b.get("k", 8)))

    return Starlette(routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Route("/v1/memory/recall", recall, methods=["POST"]),
        Route("/v1/memory/ask", ask, methods=["POST"]),
        Route("/v1/memory/consolidate", consolidate, methods=["POST"]),
        Route("/v1/memory/prune", prune, methods=["POST"]),
        Route("/v1/memory/ingest", ingest, methods=["POST"]),
        Route("/v1/federation/peers", peers, methods=["GET"]),
        Route("/v1/memory/federated_recall", federated_recall, methods=["POST"]),
    ])