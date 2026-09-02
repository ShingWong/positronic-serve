# tests/test_server.py
import sys

sys.path.insert(0, "/usr/local/devel/positronic/positronic-agent-interface")

import pytest
from starlette.testclient import TestClient

from positronic_serve.config import load_config
from positronic_serve.server import create_app


@pytest.fixture
def seeded(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.consolidate import run as consolidate
    from positronic_ai.ops.ingest import run as ingest
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    ingest(str(tmp_path), "auth-system debug session yesterday: token expiry was the root cause of the login failures", brain="kairos", arousal=0.5)
    ingest(str(tmp_path), "the JWT refresh bug in the auth-system is fixed now", brain="kairos", arousal=0.5)
    consolidate(str(tmp_path), "auth-system: token expiry was the root cause, now fixed", brain="kairos", arousal=0.5)
    return tmp_path


def test_healthz(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["brain"] == "kairos"


def test_recall_returns_peep_payload(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/recall", json={"text": "auth token expiry"})
    assert r.status_code == 200
    hits = r.json()["results"]
    assert hits, "recall should return hits"
    h = hits[0]
    assert "episode_id" in h and h.get("tau") is not None
    assert isinstance(h.get("wall"), str)
    assert h.get("kind") in ("message", "consolidation")
    assert isinstance(h.get("fallback"), bool)


def test_ask_returns_dossier(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/ask", json={"object": "auth system"})
    assert r.status_code == 200
    assert r.json().get("sightings"), "dossier should have sightings"


def test_consolidate_writes(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/consolidate", json={"text": "serve test summary", "arousal": 0.3})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["tau"] is not None


def test_ingest_writes(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/ingest", json={"text": "a new fact to remember", "arousal": 0.4})
    assert r.status_code == 200
    body = r.json()
    assert body["encoded"] is True and body["tau"] is not None


def test_prune_runs(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/prune", json={})
    assert r.status_code == 200
    assert "scanned" in r.json()


def test_peers_listing(seeded):
    cfg = load_config(seeded)
    client = TestClient(create_app(cfg))
    r = client.get("/v1/federation/peers")
    assert r.status_code == 200
    assert r.json() == {"peers": []}


def test_federated_recall_route_degrades_to_local(seeded):
    cfg = load_config(seeded)
    cfg["peers"] = ["http://localhost"]
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/federated_recall",
                    json={"text": "auth token", "k": 5})
    assert r.status_code == 200
    out = r.json()
    assert out["results"], "federated recall should return local hits"
    assert out["sources"], "sources must be non-empty"
    # TestClient is in-process only: the http://localhost peer is unreachable,
    # so federated_recall gracefully degrades to local-only results.
    assert out["sources"] == ["local"]
    assert all(h.get("source_host") == "local" for h in out["results"])


def test_single_key_wrong_token_401(seeded):
    from positronic_serve.config import load_config
    from positronic_serve.server import create_app
    cfg = load_config(seeded)
    cfg["auth"] = {"manager": "single", "key": "sekret"}
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/recall", json={"text": "auth token"},
                    headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_single_key_right_token_200(seeded):
    from positronic_serve.config import load_config
    from positronic_serve.server import create_app
    cfg = load_config(seeded)
    cfg["auth"] = {"manager": "single", "key": "sekret"}
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/recall", json={"text": "auth token"},
                    headers={"Authorization": "Bearer sekret"})
    assert r.status_code == 200


def test_single_key_no_token_401(seeded):
    from positronic_serve.config import load_config
    from positronic_serve.server import create_app
    cfg = load_config(seeded)
    cfg["auth"] = {"manager": "single", "key": "sekret"}
    client = TestClient(create_app(cfg))
    r = client.post("/v1/memory/recall", json={"text": "auth token"})
    assert r.status_code == 401