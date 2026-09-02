# positronic-serve — PEEP Network Layer (Provider + Federated Peer)

> Date: 2026-09-02
> Status: approved design — implementing
> Port: **2114** (NDR-2114, the Bicentennial Man reference — "2" for bi)

## Context and motivation

PEEP (Positronic Engram Exchange Protocol) defines the *data contract* a
polytemporal memory engine delivers to an agent. positronic-serve puts that
contract on the network as an HTTP service — brain-as-a-service — and extends
it into a *federation*: one logical brain, many hosts, each running
positronic-serve as a peer. A buyer installs the package, points it at a
brain, and sells `/v1/memory/*`. A federator runs it per host and peers them.

## Goal

A PEEP-only memory service over HTTP that (1) exposes this host's brains via
`/v1/memory/*` endpoints returning pure PEEP JSON, and (2) fans out recall to
registered remote peers and RRF-fuses results across hosts. Ships with a
pluggable auth interface and a network-protocol test/validate script.

## Non-goals

- NOT an LLM proxy — no `/v1/chat/completions`, no `/v1/models`, no
  prompt-injection conventions. This is a memory service, not a model host.
- NOT the PEEP RFC itself (that lives in positronic-research); serve is the
  *transport* for the RFC.
- NOT multi-tenant billing/quotas (a later phase — the auth seam is designed
  to allow it, but this build ships key validation, not usage accounting).

## Architecture

New public repo `github.com/ShingWong/positronic-serve` (GPL-3.0),
cloned at the umbrella root next to the other public repos (engram, PAI,
plugins); `consumers/` holds downstream consumers. Depends on
`positronic_ai` (PAI) — reuses every verb op unchanged.

```
positronic_serve/
  server.py           # ASGI app: /v1/memory/* + /healthz (+ /v1/federation/*)
  auth.py             # KeyManager interface + pluggable impls
  federation.py       # peer registry + fan-out recall + RRF fusion
  cli.py              # `positronic-serve` launcher (uvicorn/starlette)
tests/
  test_protocol.py    # the network conformance suite (test/validate script)
  test_federation.py  # two live servers, peer fan-out, RRF fusion
```

Stack: `starlette` (ASGI, minimal dep) + `uvicorn` (server). No fastapi —
the surface is small and explicit. PAI is the only domain dependency.

## HTTP surface

Base: `/v1/memory/*`. JSON bodies, `application/json` responses.

| method | path | request → response |
|---|---|---|
| POST | `/v1/memory/recall` | `{text, k?, consolidation?, context_window?}` → PEEP recall payload |
| POST | `/v1/memory/ask` | `{object}` → PEEP object dossier |
| POST | `/v1/memory/consolidate` | `{text, arousal?}` → `{tau, episode_id, encoded}` |
| POST | `/v1/memory/prune` | `{}` → prune report `{scanned, day_merged, ...}` |
| POST | `/v1/memory/ingest` | `{text, arousal?, brain?}` → `{tau, episode_id, encoded}` |
| POST | `/v1/memory/federated_recall` | `{text, k?}` → fused PEEP results across local brains + peers |
| GET | `/v1/federation/peers` | `{}` → `{peers: [url, ...]}` (list registered) |
| GET | `/healthz` | `{}` → `{ok: true, brain: <name>, peers: <n>}` |

Every memory endpoint returns the exact PEEP payload shape the PAI op
produces — the server is a *thin transport*, never a re-serializer. A hit
carries `{episode_id, tau, wall, stream, kind, salience, snippet,
fuzz_lo, fuzz_hi, provenance, person_boost, fallback}`; recall attaches the
object digest when the cue fuzzy-matches.

## Auth — two tracks (pluggable KeyManager)

The auth seam is a tiny interface so contributors ship their own enterprise
manager without touching the server:

```python
class KeyManager(Protocol):
    def validate(self, token: str | None, *, scope: str = "memory") -> bool: ...
    def describe(self) -> dict: ...   # {"manager": name, "scopes": [...]}
```

Shipped implementations:

- **`LocalKeyManager`** — dev: no key required when bound to `127.0.0.1`.
  Default track (zero config).
- **`SingleKeyManager`** — the one-key quickie: one bearer token from
  `serve.json`; `Authorization: Bearer <key>` required on non-localhost.
  Ships ready for the first sale.

Extension point: contributors implement the same `KeyManager` protocol
(`GoogleKeyManager`, `AzureKeyManager`, `AwsKeyManager`, ...) and register
it. `serve.json` selects `{"manager": "single", "key": "..."}` or
`{"manager": "local"}`; a custom manager is a module path.

## Federation

- `serve.json` `peers: ["https://brain-b.example.com", ...]` — the registry.
- `federated_recall` fans out: local brains via `ops.recall` + each peer's
  `POST /v1/memory/recall` (with this host's auth token), then **RRF-fuses**
  across sources (the engine's reciprocal-rank fusion, extended with a
  `source_host` tag per hit).
- **Resilience**: one unreachable/bad peer is skipped (log + continue) —
  mirrors the engine's federated-skip. Recall never fails on a peer.
- **Recursion guard**: peers are queried at their plain `/recall` (single
  hop), never their `/federated_recall` — no infinite federation loops.
- **Auth in federation**: outbound requests carry this host's `SingleKey`
  when configured; peers with `LocalKeyManager` accept it. Configured via
  the same auth block.

## Config (`serve.json`)

```json
{
  "host": "127.0.0.1",
  "port": 2114,
  "dir": "/path/to/project/.positronic",
  "brain": "kairos",
  "auth": { "manager": "single", "key": "..." },
  "peers": []
}
```

Defaults: host 127.0.0.1, port **2114**, auth `local`.

## Test/validate script (network conformance)

`tests/test_protocol.py` (run via pytest) + a `validate-protocol.sh` wrapper
that is the network conformance gate (exit non-zero on any failure):

1. **Seeded brain**: init a tmp brain, ingest 2-3 known episodes
   (reuse the `_seed` from `test_peep_conformance.py`), start the server on
   an ephemeral port.
2. **Endpoint conformance**: hit `/healthz`, `/v1/memory/recall`,
   `/v1/memory/ask`, `/v1/memory/consolidate`, `/v1/memory/ingest`, `/prune`
   and assert each returns a **PEEP-conformant payload** — reusing the
   existing conformance assertions (per-hit time vector, digest versions,
   provenance, fallback flag).
3. **Auth matrix**: localhost no-key works under `LocalKeyManager`; under
   `SingleKeyManager` wrong key → 401, right key → 200, no key on
   non-localhost → 401.
4. **Federation**: spawn TWO live servers (A, B); register A as B's peer;
   `federated_recall` on B returns B's local hits + A's hits tagged
   `source_host=A`; stop A and re-run — B's recall still succeeds with A
   skipped (resilience).
5. **Exit gate**: `validate-protocol.sh` runs the suite, prints a PASS/FAIL
   summary, exits non-zero on failure — the reproducible network conformance
   gate (same philosophy as the dogfood test).

## Shared vs diverged (PEEP RFC)

- PEEP RFC stays in `positronic-research/papers/positronic-prism/70-peep-spec.md`
  — the protocol definition.
- positronic-serve is the *transport* — it implements the RFC over HTTP and
  is the distribution channel. The RFC and serve evolve independently.

## Testing / verification

- `pytest tests/` green (protocol + federation).
- `validate-protocol.sh` passes end-to-end.
- PAI's own `test_peep_conformance.py` still green (unchanged — serve
  consumes, does not modify PAI).
- `ruff check` clean.

## Out of scope (recorded)

- Usage accounting / per-client quotas (auth seam allows, not built).
- TLS termination (assume reverse proxy in front; serve is plain HTTP).
- Streaming/SSE (single-shot responses for this build).
- The n=500 dataset / model fine-tune (separate queue items).