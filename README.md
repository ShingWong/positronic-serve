# positronic-serve

The **PEEP network layer** — brain-as-a-service plus federated polytemporal memory.
Serves a positronic brain over HTTP on **port 2114** (NDR-2114, "2" for bi),
exposing memory operations as JSON endpoints and fanning out recall across
peer brains.

Thin and stateless: every memory verb delegates to `positronic_ai` ops
(`recall`, `ask`, `consolidate`, `prune`, `ingest`), and federation is a
one-hop fan-out with reciprocal-rank fusion. No MCP, no direct `memeng`
access — the same rule as the agent plugins.

## Quickstart

```bash
# 1. Install the package (dev path — see note below)
pip install -e . --no-deps

# 2. Point PYTHONPATH at the PAI checkout
export PYTHONPATH=/path/to/positronic-agent-interface

# 3. Run — serve.json + .positronic live in the config dir
positronic-serve --config-dir . --port 2114
```

> **PAI dependency note:** `pyproject.toml` lists `positronic-ai` but the
> installed metadata is `positronic-agent-interface`, so the dependency is
> currently unresolvable by name. The supported dev path is
> `pip install -e . --no-deps` plus `PYTHONPATH` pointing at your
> `positronic-agent-interface` checkout. This will change once PAI ships
> resolvable metadata.

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

## Auth

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

## Federation

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

## License

GPL-3.0-or-later. Part of the positron project — see
[positronic-research](https://github.com/ShingWong/positronic-research) for
the PEEP paper and architecture.