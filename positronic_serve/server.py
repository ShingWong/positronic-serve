# positronic_serve/server.py
import json

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from positronic_serve.auth import build_key_manager


async def _body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _auth_ok(request: Request, cfg: dict) -> bool:
    mgr = build_key_manager(cfg.get("auth", {}))
    header = request.headers.get("authorization", "")
    token = header[7:] if header.startswith("Bearer ") else None
    return mgr.validate(token)


def create_app(cfg: dict):
    import sys
    sys.path.insert(0, "/usr/local/devel/positronic/positronic-agent-interface")
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

    return Starlette(routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Route("/v1/memory/recall", recall, methods=["POST"]),
        Route("/v1/memory/ask", ask, methods=["POST"]),
        Route("/v1/memory/consolidate", consolidate, methods=["POST"]),
        Route("/v1/memory/prune", prune, methods=["POST"]),
        Route("/v1/memory/ingest", ingest, methods=["POST"]),
        Route("/v1/federation/peers", peers, methods=["GET"]),
    ])