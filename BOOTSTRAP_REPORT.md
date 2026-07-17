# Agent Zero Bootstrap Report — Harness

Spec reference: `docs/SPEC.md`, frozen v1.5 copy.

## What exists now

- Python 3.12 package metadata with the C.1 runtime dependencies, locked by
  `uv.lock`, plus the installed developer entry point `harness dev`.
- FastAPI daemon factory serving the built `web/dist/` shell and accepting
  WebSocket connections at `/ws`.
- Strict Pydantic model for every C.7 envelope field and the closed set of
  eight M1 message types. A valid inbound envelope is echoed with the same
  routing fields, `type="error"`, and `payload="not implemented"`.
- Typed Pydantic bodies and a seven-method `SpineClient` surface mirroring
  the complete v1.5 C.4 contract. The shared `MemoryUnit`, context-specific
  `MemoryCard` feature/rank values, `wrong_removed`, create/PATCH attribution,
  similar-band `force`, label/revision conflicts, and stable paged-list shapes
  are all represented without transport behavior.
- React + TypeScript + Vite placeholder shell with no product behavior,
  network calls, WebSocket calls, or localhost assumption in browser code.
- Python and web lint/test/build CI, plus a separately named H2 contract-test
  skeleton gated on the configurable `SPINE_CONTRACT_IMAGE` repository
  variable.
- A tracked pre-commit scope fence, repeated over all tracked files in CI,
  which blocks the forbidden M1 feature families named by Garden Plan §7.
- Exact relay ground rules in both `AGENTS.md` and `CLAUDE.md`, an ADR-shaped
  P4 decision journal, and the B.6 judge law in `verification/README.md`.

## Deliberately stubbed

The P0 Spine service returns RFC 7807 HTTP 501 for these seven C.4 routes;
the matching Harness client methods exist but raise `NotImplementedError` and
perform no transport or business behavior:

1. `POST /v1/inject/prepare` → `SpineClient.prepare_injection`
2. `POST /v1/inject/commit` → `SpineClient.commit_injection`
3. `POST /v1/feedback` → `SpineClient.submit_feedback`
4. `POST /v1/memories` → `SpineClient.create_memory`
5. `PATCH /v1/memories/{id}` → `SpineClient.patch_memory`
6. `GET /v1/memories` → `SpineClient.list_memories`
7. `POST /v1/search` → `SpineClient.search`

`agent.py`, `memory_capability.py`, and `tools_memory.py` are importable module
placeholders only. There is no agent assembly, model call, memory flow, tool,
gate, chat, or other business logic. The WebSocket error echo is the sole P0
daemon message behavior required by C.10.

## Verification state

Bootstrap command output and scope checks are recorded in
`verification/bootstrap/README.md`, including the live C.7 echo and the
fresh v1.5 390×844 shell screenshot. The scope fence passed the repository
and rejected a staged forbidden-feature probe. The configurable contract-test
job is a skeleton and was not represented as a live Spine contract pass.
Milestone acceptance remains subject to the independent B.6/C.9 judge process.

The v1.5 P0 refresh incorporates the human resolution of Garden FLAGS
F001–F005 and SPEC D.2 entries 028–029. No new bootstrap choice was required:
the refreshed models follow the newly explicit contract. DECISIONS.md Entry
003 records that dictated adoption and explicitly supersedes Entry 001's
historical opaque-body note; it does not claim a new local contract choice.

## Where the gardeners begin

The next implementation work begins with **SPEC C.2 rules, then SPEC C.4
memory endpoints first**. On the Harness track, H1 reads **C.7 and C.1** to
turn the envelope/daemon seam into routed transport; H2 later reads **C.4** to
implement this client against the live Spine contract. No successor should
infer business behavior from these P0 stubs.
