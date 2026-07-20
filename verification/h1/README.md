# H1 envelope and daemon WebSocket evidence

This is builder evidence for packet H1, not the independent M1 verdict reserved
by SPEC B.6. H1 implements only the C.1/C.7 transport seam plus enacted Garden
A-013. Per-type payloads and browser, agent, memory, gate, and model behavior
remain owned by later packets.

## Reproducible gates

From the Harness repository root:

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check src tests
.githooks/pre-commit --all
PYTHONPATH=src uv run pytest -q
npm run lint --prefix web
npm run build --prefix web
git diff --check
```

The focused transport suite was also isolated with:

```sh
PYTHONPATH=src uv run pytest -q tests/test_envelope.py tests/test_daemon.py
```

## Recorded result — 2026-07-20

The full Harness suite completed:

```text
50 passed, 1 skipped in 0.18s
```

The skip is the intentional H2 live-Spine contract reservation. The focused H1
suite completed `35 passed in 0.15s`. Ruff lint/format, uv lock, the M1 scope
fence, diff whitespace, web ESLint, TypeScript, and the production Vite build
all passed. The web build transformed 17 modules and produced its existing
static shell without source changes.

## Live daemon probe

A real Uvicorn process served the app on loopback, and an independent
`websockets` client connected to `/ws`. It sent this valid text frame:

```json
{"v":1,"id":"01ARZ3NDEKTSV4RRFFQ69G5FAV","ts":"2026-07-20T12:00:00Z","machine_id":"machine-live","agent_id":"agent-live","thread_id":"thread-live","type":"prompt.submit","payload":{"prompt":"live H1 probe"}}
```

The daemon returned the preserved P0 fallback through the routed seam:

```json
{"agent_id":"agent-live","id":"01ARZ3NDEKTSV4RRFFQ69G5FAV","machine_id":"machine-live","payload":"not implemented","thread_id":"thread-live","ts":"2026-07-20T12:00:00Z","type":"error","v":1}
```

The same client then sent the invalid text frame `{`. It observed close code
`1008` with reason `invalid C.7 envelope`. Uvicorn logged an accepted `/ws`
connection and then shut down cleanly after the probe.

## What the checks prove

- `Envelope` requires the C.7 outer fields, permits only the two named optional
  IDs, rejects extra fields and Boolean masquerading as version 1, validates a
  bounded Crockford ULID, and exposes exactly the eight M1 message types;
- every message type has a route, injected handlers are copied per app, each
  valid envelope dispatches once by its enum type, and a handler can emit
  multiple validated envelopes for the named `run.delta` stream;
- unregistered behavior remains the historical same-shaped
  `error: not implemented` response, so H1 adds no downstream business logic;
- invalid JSON, non-object JSON, non-standard numeric constants, parser integer
  and recursion limits, missing, extra, or invalid envelope fields, and binary
  frames invoke no handler and close exactly as A-013 requires;
- a valid frame may route before a later malformed frame, after which that
  connection closes and performs no further dispatch; and
- the `/ws` route continues to coexist with both the built static shell and the
  explicit missing-build HTTP response, while unmatched WebSocket paths close
  cleanly before Starlette's HTTP-only static application.

Three read-only audits separately reviewed contract scope, repository design,
and adversarial frame/routing behavior. Their concrete findings were resolved
before handoff; no blocker remained.
