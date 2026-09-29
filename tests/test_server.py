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

# tests/test_server.py
# positronic_ai is a declared dependency; the old sys.path shim made the suite
# test the sibling checkout rather than the declared package.
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from positronic_serve.auth import mint_bound_token, public_key_b64
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


def _bound_env(seeded, trusted=None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    priv = Ed25519PrivateKey.generate()
    cfg = load_config(seeded)
    cfg["auth"] = {"manager": "bound-single",
                   "public_key": public_key_b64(priv)}
    cfg["trusted_proxies"] = trusted or []
    return priv, cfg


def _client(cfg, ip="10.66.66.9"):
    return TestClient(create_app(cfg), client=(ip, 40000))


def _claims(subnet="10.66.66.0/24", domain="testserver"):
    return {"allowed_subnet": subnet, "allowed_domain": domain}


def _post(client, token, extra_headers=None):
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(extra_headers or {})
    return client.post("/v1/memory/recall",
                       json={"text": "auth token expiry"},
                       headers=headers)


def _audit_records(seeded):
    path = Path(seeded, "audit.log")
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def test_bound_matching_identity_200(seeded):
    priv, cfg = _bound_env(seeded)
    token = mint_bound_token(priv, _claims())
    assert _post(_client(cfg), token).status_code == 200


def test_bound_rogue_subnet_401_writes_metadata_audit(seeded):
    priv, cfg = _bound_env(seeded)
    token = mint_bound_token(priv, _claims())
    r = _post(_client(cfg, ip="192.168.5.7"), token)
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    assert token not in r.text and "Traceback" not in r.text
    recs = _audit_records(seeded)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["decision"] == "deny_bound_mismatch"
    assert rec["scheme"] == "bound-single"
    assert rec["origin"] == "192.168.5.7"
    assert rec["allowed_subnet"] == "10.66.66.0/24"
    assert rec["allowed_domain"] == "testserver"
    assert rec["path"] == "/v1/memory/recall"
    assert rec["key_id"] and rec["request_id"] and rec["ts"]
    assert isinstance(rec["tau"], int)
    text = Path(seeded, "audit.log").read_text()
    assert token not in text and "PRIVATE" not in text


def test_bound_rogue_domain_401(seeded):
    priv, cfg = _bound_env(seeded)
    token = mint_bound_token(priv, _claims(domain="evil.example"))
    assert _post(_client(cfg), token).status_code == 401
    assert _audit_records(seeded)[0]["allowed_domain"] == "evil.example"


def test_bound_ignores_forwarding_header_from_untrusted_peer(seeded):
    priv, cfg = _bound_env(seeded)          # trusted_proxies stays empty
    token = mint_bound_token(priv, _claims())
    r = _post(_client(cfg), token, {"X-Forwarded-For": "192.168.5.7"})
    assert r.status_code == 200   # origin is still the direct peer


def test_bound_honors_forwarding_header_from_trusted_peer(seeded):
    priv, cfg = _bound_env(seeded, trusted=["10.66.66.0/24"])
    client = _client(cfg)                    # peer 10.66.66.9 is trusted
    outside = mint_bound_token(priv, _claims(subnet="10.66.66.0/24"))
    r = _post(client, outside, {"X-Forwarded-For": "192.168.5.7"})
    assert r.status_code == 401   # XFF consulted: origin moved off-peer
    forwarded = mint_bound_token(priv, _claims(subnet="192.168.5.0/24"))
    r = _post(client, forwarded, {"X-Forwarded-For": "192.168.5.7"})
    assert r.status_code == 200


def test_bound_xff_rightmost_untrusted_hop_is_origin(seeded):
    priv, cfg = _bound_env(seeded, trusted=["10.66.66.0/24"])
    token = mint_bound_token(priv, _claims(subnet="1.2.3.0/24"))
    r = _post(_client(cfg), token,
              {"X-Forwarded-For": "1.2.3.4, 10.66.66.9"})
    assert r.status_code == 200
    # origin is 1.2.3.4, not the trusted hop itself
    hop_only = mint_bound_token(priv, _claims(subnet="10.66.66.9/32"))
    r = _post(_client(cfg), hop_only,
              {"X-Forwarded-For": "1.2.3.4, 10.66.66.9"})
    assert r.status_code == 401


def test_bound_all_trusted_hops_fall_back_to_leftmost(seeded):
    priv, cfg = _bound_env(seeded, trusted=["10.66.66.0/24"])
    token = mint_bound_token(priv, _claims(subnet="10.66.66.8/32"))
    r = _post(_client(cfg), token,
              {"X-Forwarded-For": "10.66.66.8, 10.66.66.9"})
    assert r.status_code == 200   # every hop trusted: leftmost wins