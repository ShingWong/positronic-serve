# positronic-serve — the PEEP network layer

### Client/server polytemporal memory — share a brain, federate across hosts

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Protocol: PEEP](https://img.shields.io/badge/Protocol-PEEP-orange)]()
[![Port](https://img.shields.io/badge/Port-2114-green)]()
[![Federation](https://img.shields.io/badge/Federation-RRF%20fusion-blueviolet)]()

Positronic-serve turns a positronic brain into a **network service** — a
client/server model where one host owns a brain and any number of clients
(agents, other hosts, your own services) query it over HTTP on **port 2114**
(NDR-2114, "2" for bi).

It is the transport layer for **PEEP** (Positronic Engram Exchange Protocol):
the same polytemporal data contract your agent plugins speak, now served as
JSON endpoints any consumer can call. One brain, exposed. Many brains,
federated into one logical memory.

---

## Table of Contents

- [Why positronic-serve?](#why-positronic-serve)
- [The client/server model — sharing a brain](#the-clientserver-model--sharing-a-brain)
- [What it enables](#what-it-enables)
- [Endpoints](#endpoints)
- [Auth — two tracks, pluggable](#auth--two-tracks-pluggable)
- [Federation — one logical brain, many hosts](#federation--one-logical-brain-many-hosts)
- [Install](#install)
- [Quick start](#quick-start)
- [Conformance gate](#conformance-gate)
- [License](#license)

---

## Why positronic-serve?

Your positronic brain already remembers, curates, and recalls fast — but it
sits on a disk, reachable only by the process that opens it. The server is the
**boundary** that makes that memory addressable:

- **Brain as a service** — expose a brain over HTTP and sell or share the
  capability: query, ingest, consolidate, prune, all remote.
- **Brain federation** — run a server per host, register peers, and recall
  across all of them as one logical brain.
- **Protocol standardization** — every endpoint returns the exact **PEEP**
  payload, so any consumer that speaks PEEP can adopt the contract without
  coupling to the engine that produced it.
- **Thin and stateless** — every memory verb delegates to `positronic_ai`
  ops (`recall`, `ask`, `consolidate`, `prune`, `ingest`); federation is a
  one-hop fan-out with reciprocal-rank fusion. No MCP, no direct `memeng`
  access — the same rule as the agent plugins.
- **Pluggable auth** — localhost for development, a single bearer key for the
  first sale, and a `KeyManager` seam for enterprise modules (Google, Azure,
  AWS, OAuth).

---

## The client/server model — sharing a brain

The core shape is **one server, many clients**:

```
        client A (agent) ─┐
        client B (service)─┤  POST /v1/memory/*   ┌──────────────────────┐
        client C (other    └──────────────────────▶ │  positronic-serve   │
                 host)                             │  port 2114           │
                                                   │  .positronic/brains/ │
        peer server (10.0.0.6:2114) ──────────────▶│  kairos, mail, ...   │
        (federated recall fan-out)                 └──────────────────────┘
```

- The **server** owns the brains (`.positronic/brains/*` under the config
  dir). It never calls out on its own — it *answers*.
- The **clients** are anything that can speak HTTP + PEEP: an agent plugin,
  a fleet service, a dashboard, or another positronic-serve host acting as a
  peer.
- The server is **stateless** — it holds no conversation, no session, no
  index of its own. Each request is a PEEP op against the shared brain.

This is what makes brain *sharing* possible: the brain stops being a private
file and becomes a resource other components depend on — with one owner, one
retention policy, and a single source of truth.

---

## What it enables

| Capability | How positronic-serve delivers it |
|---|---|
| **Brain as a service** | Expose `/v1/memory/*` to paying or internal clients; the brain is the product. |
| **Agent memory over the network** | Any agent on the LAN (or the internet, behind a reverse proxy) queries the same brain instead of opening the SQLite file. |
| **Federated recall** | `POST /v1/memory/federated_recall` fans out to registered peers, RRF-fuses the hits, tags each with `source_host`. |
| **Cross-host memory** | Run a server per host, register peers, and query them all as one logical brain — a federation of memory. |
| **Protocol adoption** | Every response is a PEEP payload; adopt the contract, decouple from the engine. |
| **The email-archival appliance** | The appliance's semantic-query layer is exactly this: a brain served over HTTP, queried by the investigation UI. |

---

## Endpoints

| method | path | body | returns |
|--------|------|------|---------|
| `GET` | `/healthz` | — | `{ok, brain, peers}` liveness probe |
| `POST` | `/v1/memory/recall` | `{text, k?, consolidation?, context_window?}` | PEEP recall hits (each with `episode_id`, `tau`, `wall`, `kind`, `fallback`) |
| `POST` | `/v1/memory/ask` | `{object}` | entity dossier for the named object |
| `POST` | `/v1/memory/consolidate` | `{text, brain?, arousal?}` | consolidation summary event |
| `POST` | `/v1/memory/prune` | `{}` | run τ-decay pruning on the live brain |
| `POST` | `/v1/memory/ingest` | `{text, brain?, arousal?}` | ingest a new memory |
| `POST` | `/v1/memory/federated_recall` | `{text, k?}` | local + peer recall, RRF-fused |
| `GET` | `/v1/federation/peers` | — | `{peers: [...]}` configured peer list |

`/healthz` and `/v1/federation/peers` are public. All `/v1/memory/*` routes
require authorization (see below).

---

## Auth — two tracks, pluggable

Two tracks, both driven by the `auth` block in `serve.json`:

1. **Local (dev)** — `{"manager": "local"}`: no key required. For localhost
   development only; do not bind non-local interfaces with this track.
2. **Single key** — `{"manager": "single", "key": "…"}`: one shared bearer
   token. Send `Authorization: Bearer <key>` on every memory request; missing
   or wrong tokens get `401`.

### KeyManager extension seam

Auth is pluggable via a tiny protocol in `positronic_serve/auth.py`:

```python
class KeyManager(Protocol):
    def validate(self, token: str | None, *, scope: str = "memory") -> bool: ...
    def describe(self) -> dict: ...
```

`build_key_manager` maps a `manager` string to an implementation. To ship your
own (Google, Azure, AWS, OAuth, …), implement `KeyManager`, register it in the
`_MANAGERS` dict, and set the matching `manager` name in `serve.json`. The
server never touches auth internals — it only calls `validate()`.

---

## Federation — one logical brain, many hosts

Add peer base URLs to `serve.json`:

```json
{
  "auth": { "manager": "single", "key": "sekret" },
  "peers": ["http://10.0.0.5:2114", "http://10.0.0.6:2114"]
}
```

`POST /v1/memory/federated_recall` then:

1. runs **local recall** on the configured brain,
2. fans out to each peer's `/v1/memory/recall` (one hop, same
   `Authorization: Bearer <key>` when the manager is `single`),
3. **RRF-fuses** the hit lists (reciprocal-rank, dedup by `episode_id`, each
   hit tagged `source_host`), and
4. returns `{results, sources}`.

A bad or unreachable peer is **skipped, never fatal** — recall degrades to the
healthy subset. The fan-out is strictly single-hop (peers do not recurse), so
there is no federation loop.

---

## Install

```bash
# 1. Install the package (pulls positronic-agent-interface automatically)
pip install -e .

# 2. Run — serve.json + .positronic live in the config dir
positronic-serve --config-dir . --port 2114
```

The `positronic-agent-interface` dependency resolves directly from the
`feat/pai` branch of its repo — no `--no-deps`, no manual `PYTHONPATH`.

The server reads `serve.json` from the config dir (defaults apply when absent):

```json
{
  "host": "127.0.0.1",
  "port": 2114,
  "dir": ".",
  "brain": "kairos",
  "auth": { "manager": "local" },
  "peers": []
}
```

| key | default | meaning |
|-----|---------|---------|
| `host` | `127.0.0.1` | bind address |
| `port` | `2114` | bind port |
| `dir` | config dir | project dir holding `.positronic/brains` |
| `brain` | `kairos` | default brain name |
| `auth` | `{manager: local}` | key manager config (see Auth) |
| `peers` | `[]` | federated peer base URLs (see Federation) |

CLI flags override config: `--config-dir`, `--host`, `--port`, `--reload`.

---

## Quick start

**Serve a brain, query it from anywhere:**

```bash
# terminal 1 — the server
positronic-serve --config-dir . --port 2114

# terminal 2 — a client
curl -s -X POST http://127.0.0.1:2114/v1/memory/recall \
  -H 'Content-Type: application/json' \
  -d '{"text":"what did we decide about the paper"}' \
  | python3 -m json.tool

# write a new memory remotely
curl -s -X POST http://127.0.0.1:2114/v1/memory/ingest \
  -H 'Content-Type: application/json' \
  -d '{"text":"the serve layer went live today"}' \
  | python3 -m json.tool
```

**Federate two hosts:**

```bash
# host B registers host A as a peer
# B:  {"peers": ["http://10.0.0.5:2114"]}
curl -s -X POST http://127.0.0.1:2114/v1/memory/federated_recall \
  -H 'Content-Type: application/json' \
  -d '{"text":"anything, anywhere"}'
# → {results: [...], sources: ["local", "http://10.0.0.5:2114"]}
```

---

## Conformance gate

`./validate-protocol.sh` is the network protocol conformance gate. It seeds a
tmp brain, boots the server, and checks:

- all endpoints answer with the expected status (healthz, PEEP memory routes, peers),
- PEEP payload shape (recall hits carry the full time vector: `episode_id`,
  `tau`, `wall`, `kind`, `fallback`),
- the auth matrix (no token / wrong token → 401, correct token → 200), and
- live two-server federation (a real peer appears in `sources`).

It exits `0` iff every check passes; any failure exits non-zero:

```bash
./validate-protocol.sh && echo "PROTOCOL GATE: PASS"
```

Local test suite (unit + in-process federation):

```bash
pytest tests/ -q
ruff check positronic_serve/ tests/
```

---

## License

GPL-3.0-or-later. Part of the positron project — see
[positronic-research](https://github.com/ShingWong/positronic-research) for
the PEEP paper and architecture, and
[positronic-agent-interface](https://github.com/ShingWong/positronic-agent-interface)
for the ops layer this server delegates to.