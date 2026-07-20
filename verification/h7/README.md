# H7 verification — C.7 v1.12 loop controls

H7 implements the enacted Garden A-016 wire contract and ADR-014's M1
cancel/queue/snapshot/usage subset. It does not implement the H4 browser, H5
memory-gate decision flow, or any reserved M3 behavior.

## Trace

- `src/harness/envelope.py` validates every H7 payload, all four terminal
  reasons, typed deltas, cumulative usage, snapshot state, fresh daemon
  envelopes, and open-ended reserved/unknown JSON types.
- `src/harness/run_protocol.py` is the framework-neutral model-run seam.
- `src/harness/run_loop.py` owns daemon-lifetime per-thread state, one active
  run, FIFO prompts, cancellation terminalization, snapshots, gates, bounded
  subscriber delivery, and exactly-once terminal ordering.
- `src/harness/agent_runtime.py` maps pydantic-ai events and usage into the
  owned seam, preserves captured partial history, and repairs cancelled tool
  calls with public terminal interrupted returns.
- `src/harness/daemon.py` keeps the socket reader live while runs execute,
  serializes each connection through a bounded outbox, forwards or ignores
  extension types, and composes the real agent plus one Spine client for
  `harness dev`.

## Reproducible gates

Run from `Harness/`:

```sh
PYTHONPATH=src uv run pytest -q -m 'not contract'
PYTHONPATH=src uv run pytest -q \
  tests/test_envelope.py tests/test_run_loop.py \
  tests/test_agent_runtime.py tests/test_daemon.py
PYTHONASYNCIODEBUG=1 PYTHONPATH=src uv run pytest -q \
  -W error::RuntimeWarning tests/test_run_loop.py tests/test_daemon.py
uv run ruff check .
uv run ruff format --check src tests
uv lock --check
.githooks/pre-commit --all
npm run lint --prefix web
npm run build --prefix web
git diff --check
sh tests/contract/run.sh
```

Recorded on 2026-07-20:

- 217 non-contract tests passed; 2 live contract tests were deselected.
- 102 focused H7 cases passed.
- 40 loop/daemon cases passed with asyncio debug and RuntimeWarnings fatal.
- Ruff lint/format, lock, M1 scope, web lint/build, and diff checks passed.
- The disposable migrated Spine contract passed 2 tests and tore down cleanly.
- The sibling Spine suite passed 158 tests with
  `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` on Colima.

All model-path tests use pydantic-ai FunctionModel/TestModel with hosted calls
disabled. The cancellation fixture blocks inside the real `search_memory`
tool, verifies teardown before confirmation, asserts the inserted interrupted
ToolReturnPart, and successfully reuses that history on the next turn.

## Live daemon probe

A real Uvicorn process ran `harness.daemon:create_app` on loopback and a
separate `websockets` client submitted one prompt. It observed, in order:

```text
run.started -> run.usage -> run.done(error, partial=true)
```

The default injectable factory intentionally has no trusted model context; the
developer command uses `create_dev_app`, whose FunctionModel integration test
ends `run.done(end_turn)` after a streamed text delta. In the live probe all
three outer envelope IDs were fresh, all lifecycle payloads shared one run ID,
and run.started retained the inbound prompt ID. Reconnecting returned
thread.snapshot first with the two transcript messages. An unknown extension
was then ignored without an error, and an explicit snapshot request still
returned the authoritative snapshot.

## Adversarial evidence

Independent read-only audits probed contract parsing, asyncio races, slow
consumers, and the pydantic-ai cancellation seam. Their concrete findings are
locked into regressions: non-finite JSON rejection; request-first snapshot
union selection; pre-start and finish/cancel races; no second cancellation
during tool cleanup; snapshot-before-direct-response ordering; one bounded
worker rather than one task per delta; `/remember` budget/provider terminal
classification; and cancellation repair even when tool cleanup raises.
