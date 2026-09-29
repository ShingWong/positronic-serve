#!/usr/bin/env bash
# =====================================================================
# positronic-serve — network protocol conformance gate
# Starts the server on a tmp brain, exercises every endpoint, verifies
# PEEP payloads + auth + federation. Exit non-zero on any failure.
# =====================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
TMP2=""
PORT=21140
# positronic_ai is a declared dependency, so it needs no path entry here. Only
# this checkout goes on PYTHONPATH, so `python3 -m positronic_serve` runs the
# tree under test. The old absolute entry was redundant and, because it was
# prepended, it made the sibling checkout shadow the declared install.
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

cleanup() { kill "${SRV_PID:-}" "${SRV_PID2:-}" 2>/dev/null || true; rm -rf "$TMP" "$TMP2"; }
trap cleanup EXIT

echo "== seeding brain =="
python3 - "$TMP" <<'EOF'
import sys
from positronic_ai.brains import init_brain
from positronic_ai.ops.ingest import run as ingest
from positronic_ai.ops.consolidate import run as consolidate
d = sys.argv[1]
init_brain(d, "kairos", "balanced", "lexical")
ingest(d, "auth-system debug session yesterday: token expiry was the root cause of the login failures", brain="kairos", arousal=0.5)
ingest(d, "the JWT refresh bug in the auth-system is fixed now", brain="kairos", arousal=0.5)
consolidate(d, "auth-system: token expiry was the root cause, now fixed", brain="kairos", arousal=0.5)
print("seeded")
EOF

echo "== starting server on :$PORT =="
python3 -m positronic_serve --config-dir "$TMP" --host 127.0.0.1 --port "$PORT" &
SRV_PID=$!
sleep 2

fail=0
check() { # check <desc> <expected_status> <curl args...>
  local desc="$1"; shift
  local want="$1"; shift
  local got
  got=$(curl -s -o /dev/null -w "%{http_code}" "$@")
  if [ "$got" = "$want" ]; then
    echo "  [PASS] $desc"
  else
    echo "  [FAIL] $desc (got $got, want $want)"
    fail=1
  fi
}

echo "== healthz =="
check "healthz 200" 200 http://127.0.0.1:$PORT/healthz

echo "== PEEP endpoints =="
check "recall 200" 200 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -d '{"text":"auth token expiry"}'
check "ask 200" 200 -X POST http://127.0.0.1:$PORT/v1/memory/ask \
  -H 'Content-Type: application/json' -d '{"object":"auth system"}'
check "consolidate 200" 200 -X POST http://127.0.0.1:$PORT/v1/memory/consolidate \
  -H 'Content-Type: application/json' -d '{"text":"serve conformance summary","arousal":0.3}'
check "ingest 200" 200 -X POST http://127.0.0.1:$PORT/v1/memory/ingest \
  -H 'Content-Type: application/json' -d '{"text":"a fact for the conformance gate","arousal":0.4}'
check "prune 200" 200 -X POST http://127.0.0.1:$PORT/v1/memory/prune -H 'Content-Type: application/json' -d '{}'
check "peers 200" 200 http://127.0.0.1:$PORT/v1/federation/peers

echo "== PEEP payload shape (recall hit must carry time vector) =="
RECALL=$(curl -s -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -d '{"text":"auth token expiry"}')
echo "$RECALL" | python3 -c "
import sys, json
d = json.load(sys.stdin)
hits = d.get('results', [])
assert hits, 'no hits'
h = hits[0]
assert 'episode_id' in h and h.get('tau') is not None, 'missing episode_id/tau'
assert isinstance(h.get('wall'), str), 'missing wall'
assert h.get('kind') in ('message','consolidation'), 'bad kind'
assert isinstance(h.get('fallback'), bool), 'bad fallback'
print('  [PASS] PEEP per-hit time vector + salience/kind/fallback')
"

echo "== auth: single key track =="
kill "$SRV_PID" 2>/dev/null; sleep 1
python3 - "$TMP" "$PORT" <<'EOF'
import json, sys, os
d, port = sys.argv[1], sys.argv[2]
open(f"{d}/serve.json","w").write(json.dumps({
  "host":"127.0.0.1","port":int(port),
  "auth":{"manager":"single","key":"sekret"},
  "peers":[]}))
EOF
python3 -m positronic_serve --config-dir "$TMP" --host 127.0.0.1 --port "$PORT" &
SRV_PID=$!
sleep 2
check "single-key: no token 401" 401 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -d '{"text":"auth"}'
check "single-key: wrong token 401" 401 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer wrong' -d '{"text":"auth"}'
check "single-key: right token 200" 200 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sekret' -d '{"text":"auth"}'

echo "== federation: two live servers =="
TMP2="$(mktemp -d)"
python3 - "$TMP2" <<'EOF'
import sys
from positronic_ai.brains import init_brain
from positronic_ai.ops.ingest import run as ingest
d = sys.argv[1]
init_brain(d, "kairos", "balanced", "lexical")
ingest(d, "hummingbirds migrate across the gulf each spring", brain="kairos", arousal=0.5)
print("seeded server 2")
EOF

PORT2=$((PORT+1))
python3 - "$TMP2" "$PORT2" "$PORT" <<'EOF'
import json, sys
d, port, peer_port = sys.argv[1], sys.argv[2], sys.argv[3]
open(f"{d}/serve.json","w").write(json.dumps({
  "host":"127.0.0.1","port":int(port),
  "auth":{"manager":"single","key":"sekret"},
  "peers":[f"http://127.0.0.1:{peer_port}"]}))
EOF
python3 -m positronic_serve --config-dir "$TMP2" --host 127.0.0.1 --port "$PORT2" &
SRV_PID2=$!
sleep 2

FED=$(curl -s -X POST http://127.0.0.1:$PORT2/v1/memory/federated_recall \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sekret' \
  -d '{"text":"auth token expiry"}')
if FED_OUT=$(echo "$FED" | python3 -c "
import sys, json
d = json.load(sys.stdin)
peer = 'http://127.0.0.1:$PORT'
sources = d.get('sources', [])
assert peer in sources, 'remote host missing from sources'
assert d.get('results'), 'no fused hits'
print('  [PASS] live federation: two servers, peer ' + peer + ' in sources')
"); then
  echo "$FED_OUT"
else
  echo "  [FAIL] live federation: remote host did not appear in sources"
  fail=1
fi

echo "== auth: bound-single (zero-trust identity) =="
kill "$SRV_PID" 2>/dev/null; sleep 1
python3 - "$TMP" "$PORT" <<'EOF'
import json, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from positronic_serve.auth import mint_bound_token, public_key_b64
d, port = sys.argv[1], sys.argv[2]
priv = Ed25519PrivateKey.generate()
open(f"{d}/serve.json", "w").write(json.dumps({
    "host": "127.0.0.1", "port": int(port),
    "auth": {"manager": "bound-single", "public_key": public_key_b64(priv)},
    "trusted_proxies": [],
    "peers": []}))
tokens = {
    "a": {"allowed_subnet": "10.66.66.0/24", "allowed_domain": "rogue.invalid"},
    "b": {"allowed_subnet": "127.0.0.0/8", "allowed_domain": "localhost"},
    "c": {"allowed_subnet": "127.0.0.0/8", "allowed_domain": "evil.example"},
}
for name, claims in tokens.items():
    open(f"{d}/token.{name}", "w").write(mint_bound_token(priv, claims))
print("bound-single configured, tokens a/b/c minted")
EOF
python3 -m positronic_serve --config-dir "$TMP" --host 127.0.0.1 --port "$PORT" &
SRV_PID=$!
sleep 2
TOK_A=$(cat "$TMP/token.a")
TOK_B=$(cat "$TMP/token.b")
TOK_C=$(cat "$TMP/token.c")

check "test 5: rogue subnet 401" 401 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Host: localhost' \
  -H "Authorization: Bearer $TOK_A" -d '{"text":"auth"}'
BODY_A=$(curl -s -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Host: localhost' \
  -H "Authorization: Bearer $TOK_A" -d '{"text":"auth"}')
if AUDIT_OUT=$(python3 - "$TMP" "$TOK_A" <<'EOF'
import json, sys, pathlib
d, token = sys.argv[1], sys.argv[2]
log = pathlib.Path(d, "audit.log")
assert log.exists(), "audit.log missing"
text = log.read_text()
recs = [json.loads(l) for l in text.splitlines() if l.strip()]
deny = [r for r in recs if r.get("decision") == "deny_bound_mismatch"]
assert deny, "no deny_bound_mismatch record"
r = deny[0]
assert r.get("scheme") == "bound-single", r
assert r.get("origin") in ("127.0.0.1", "::1"), f"origin {r.get('origin')!r}"
assert r.get("allowed_subnet") == "10.66.66.0/24", r
assert r.get("allowed_domain") == "rogue.invalid", r
assert r.get("path") == "/v1/memory/recall", r
assert r.get("key_id") and r.get("request_id") and r.get("ts"), r
assert isinstance(r.get("tau"), int), r
assert token not in text, "raw token leaked into audit.log"
print("  [PASS] audit: deny_bound_mismatch recorded, origin+claims echoed, no token material")
EOF
); then echo "$AUDIT_OUT"; else
  echo "  [FAIL] audit record assertions"
  fail=1
fi
if LEAK_OUT=$(python3 - "$TOK_A" "$BODY_A" <<'EOF'
import json, sys
token, body = sys.argv[1], sys.argv[2]
assert json.loads(body) == {"error": "unauthorized"}, body
for needle in ("Traceback", "Secret", "PRIVATE", "ed25519", token):
    assert needle not in body, f"body leaks {needle!r}"
print("  [PASS] 401 body: generic JSON only — no stack, no key material, no token")
EOF
); then echo "$LEAK_OUT"; else
  echo "  [FAIL] 401 body leak assertions"
  fail=1
fi
check "test 5: matching identity 200 (positive control)" 200 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Host: localhost' \
  -H "Authorization: Bearer $TOK_B" -d '{"text":"auth"}'
check "test 5: domain mismatch 401" 401 -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Host: localhost' \
  -H "Authorization: Bearer $TOK_C" -d '{"text":"auth"}'

echo "== auth: bounded uniform rejection (PEEP-0002 3.4 / 4.5) =="
# These tokens are UNSIGNED, so they exercise the pre-signature parse path that
# test 5 never reaches. Each must be denied with the same generic 401 as any
# other invalid token -- never a 5xx. A server that answers differently for an
# unparseable token has turned its parser into an oracle.
python3 - "$TMP" <<'EOF'
import base64, json, pathlib, sys
d = pathlib.Path(sys.argv[1])

def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

hdr = b64u(json.dumps({"alg": "EdDSA", "kid": "0" * 16}).encode())
sig = b64u(b"\x00" * 64)

# 1. deeply nested JSON: json.loads raises RecursionError, which is a
#    RuntimeError, not a ValueError -- it must not escape the token parser
deep = 10000
cases = {
    # nesting deep enough to blow a recursive parser's stack
    "nested": f"{hdr}.{b64u(('[' * deep + ']' * deep).encode())}.{sig}",
    # segment longer than the 4096-character bound
    "oversize": f"{b64u(b'x' * 20000)}.{b64u(b'x' * 20000)}.{sig}",
    # under the length bound, but undecodable / unparseable
    "badb64": f"{hdr}.!!!!.{sig}",
    "notjson": f"{hdr}.{b64u(b'this is not json')}.{sig}",
    "deepish": f"{hdr}.{b64u(('[' * 1400 + ']' * 1400).encode())}.{sig}",
}
for name, tok in cases.items():
    (d / f"hostile.{name}").write_text(tok)
print(f"  minted {len(cases)} unsigned hostile tokens (largest {max(len(t) for t in cases.values())} chars)")
EOF

for CASE in nested oversize badb64 notjson deepish; do
  TOK_X=$(cat "$TMP/hostile.$CASE")
  check "test 6: $CASE token 401 (not 5xx)" 401 \
    -X POST http://127.0.0.1:$PORT/v1/memory/recall \
    -H 'Content-Type: application/json' -H 'Host: localhost' \
    -H "Authorization: Bearer $TOK_X" -d '{"text":"auth"}'
  # same generic body as every other invalid token, and no 5xx anywhere
  CODE=$(curl -s -o "$TMP/hostile.$CASE.body" -w "%{http_code}" \
    -X POST http://127.0.0.1:$PORT/v1/memory/recall \
    -H 'Content-Type: application/json' -H 'Host: localhost' \
    -H "Authorization: Bearer $TOK_X" -d '{"text":"auth"}')
  if [ "$CODE" -ge 500 ] 2>/dev/null; then
    echo "  [FAIL] test 6: $CASE token produced a server error ($CODE)"
    fail=1
  fi
done

if HOSTILE_OUT=$(python3 - "$TMP" <<'EOF'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
generic = {"error": "unauthorized"}
for name in ("nested", "oversize", "badb64", "notjson", "deepish"):
    raw = (d / f"hostile.{name}.body").read_text()
    assert json.loads(raw) == generic, f"{name}: body is not the generic denial: {raw[:120]!r}"
    for needle in ("Traceback", "RecursionError", "Error", "token"):
        assert needle not in raw, f"{name}: body leaks {needle!r}"
print("  [PASS] test 6: every hostile token got the identical generic 401 body")
EOF
); then echo "$HOSTILE_OUT"; else
  echo "  [FAIL] test 6: hostile token body assertions"
  fail=1
fi

# positive control: the bounds must not break a legitimate token
check "test 6: valid token still 200 (positive control)" 200 \
  -X POST http://127.0.0.1:$PORT/v1/memory/recall \
  -H 'Content-Type: application/json' -H 'Host: localhost' \
  -H "Authorization: Bearer $TOK_B" -d '{"text":"auth"}'

echo ""
if [ "$fail" = "1" ]; then
  echo "== PROTOCOL GATE: FAIL =="
  exit 1
fi
echo "== PROTOCOL GATE: PASS =="