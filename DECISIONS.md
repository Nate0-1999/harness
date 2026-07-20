# Decision journal

## 000 — Relay law [P4]

> Read docs/SPEC.md 1 -> 2 -> B -> C before touching dirt. Every entry in this journal cites a Problem Tree node. Local defects follow the Blight Protocol (SPEC 2.1). Features that cannot name their problem do not get built.

## 001 — Bootstrap tooling [P4]

**Decision.** Package the Python 3.12 daemon with Hatchling; expose the
required `harness dev` command as a project script; use Ruff and pytest for
the bootstrap gates; use a minimal Vite + React + TypeScript web scaffold
with npm's committed lockfile and ESLint; validate C.7 envelopes strictly
with Pydantic v2; keep C.4 response shapes that the spec does not define (the
PATCH "unit", PATCH conflict, and paged list) as opaque JSON objects; and
make `harness dev` run the locked web install/build before binding the
development daemon to loopback port 8765.

**Motivation.** These choices keep package metadata, developer commands,
dependency graphs, and CI checks deterministic; provide the literal C.1
React/TS/Vite boundary without implementing H4 behavior; make the literal
C.7 seam executable immediately; avoid manufacturing missing C.4 contract
fields; make the documented developer command sufficient on a fresh clone;
and provide a deterministic local port without encoding localhost into
browser code or messages.

**Rejected alternatives.** A bespoke task runner, an unpinned frontend
dependency graph, and a larger UI framework add bootstrap machinery without
P0 capability. Server rendering would erase the explicit C.1 web boundary.
Requiring a separate undocumented web build would make the P0 developer
command incomplete, while committing generated `dist/` assets would create
source/build drift.
Permissive envelope parsing weakens the relay seam. Inventing pagination or
memory-unit fields would turn an implementation guess into cross-repository
law. Binding publicly by default needlessly enlarges the P0 surface.

## 002 — Tracked M1 scope fence [P4]

**Decision.** Keep a repository-owned pre-commit hook that scans staged files
for the forbidden M1 feature families named by Garden Plan §7, and run the
same check over all tracked files in CI. Exclude the hook itself, frozen law,
decision/report Markdown, lockfiles, and verification artifacts from the
pattern scan; those files necessarily name forbidden concepts while defining
or evidencing the boundary.

**Motivation.** A local-only hook configuration disappears on clone. Tracking
the small POSIX script and repeating it in CI makes the scope boundary visible
and reproducible without adding a hook framework.

**Rejected alternatives.** A dependency-heavy pre-commit framework adds no
useful P0 capability. Scanning `docs/SPEC.md` or the hook's own pattern list
would make every run fail on the words that define the prohibition.

## 003 — Adopt the enacted v1.5 C.4 completion [P1.1]

**Decision.** This is an adoption record, not a local contract choice. The
human-enacted SPEC v1.5 resolution in Garden FLAGS F001–F005 and SPEC D.2
entry 028 supersedes Entry 001's temporary opaque C.4 response models. Mirror
the enacted shared `MemoryUnit`; context-specific `MemoryCard` feature/rank
values; `wrong_removed`; create/PATCH `machine_id`; create `force`; label and
revision conflicts; exact create/PATCH/list responses; and `limit`/`offset`
query fields in the typed Harness seam.

**Motivation.** The two repositories couple through C.4. Recording the
supersession keeps the append-only journal historically honest while making
the current human-approved contract unambiguous to H2 and later readers.

**Rejected alternatives.** Rewriting Entry 001 would erase why P0 originally
refused to invent contract law. Leaving its opaque-model note as the journal's
last word would misdirect H2. Declaring a competing local completion would be
both redundant and beyond P0 authority because v1.5 already supplies the law.

## 004 — Closed-set WebSocket routing without payload invention [P3]

**Decision.** Adopt Garden A-013 for inbound C.7 framing. Parse one strict JSON
text frame at a time, reject binary, invalid, non-object, or schema-invalid
frames with the enacted 1008 close, and dispatch each validated envelope once
through a complete `MessageType` route table. Let the app factory copy optional
handler overrides; each async handler receives the validated envelope and an
envelope-only sender so it may emit zero or multiple C.7 messages. Preserve the
P0 `error: not implemented` response as the default route for every type until
a later packet supplies that type's behavior. Register a final WebSocket-only
catch-all before the root static mount so unknown socket paths close cleanly
instead of entering Starlette's HTTP-only static application.

**Motivation.** The copied table avoids shared mutable connection state while
making routing directly testable. A sender callback is the smallest transport
shape that can carry C.7's streamed `run.delta` messages without coupling a
handler to FastAPI or prematurely defining payloads. Exact outer validation
keeps malformed input out of every later business handler.

**Rejected alternatives.** Per-type payload models, browser-versus-daemon
direction rules, acknowledgements, and correlation semantics are absent from
C.7 and belong to later behavior packets. A global mutable registry would leak
handlers across app instances and tests. Passing the raw WebSocket into
handlers would couple business code to transport, while a one-response return
value would make the named stream type dishonest. Swallowing handler failures
into a new error schema would invent behavior the contract does not define.

## 005 — Literal Spine boundary with a hermetic live contract [P1.1]

**Decision.** Adopt the current C.4 surface, including Garden A-014's positive
prepare-context bound, A-012's search bound, the enacted list bounds, and the
v1.6 `origin_path` fields. Give each `SpineClient` one owned asynchronous HTTP
client; ownership includes any caller-supplied test transport and ends through
`aclose` or the async context manager. Send relative C.4 routes beneath a
validated, credential-free absolute HTTP(S) base URL with bearer auth, no
redirects, no retries, and JSON bodies that omit optional nulls. Validate each
response against its exact status, media type, strict standard-JSON body model,
and RFC7807 semantics without scalar coercion. Surface RFC7807 responses,
create conflicts, and PATCH conflicts as distinct typed exceptions that retain
the raw response without copying its body or credentials into exception text.

Run S1–S2 contract assertions in an unconditional CI job against the production
Spine Dockerfile at commit `9c51c992b6103ee7492961bcb27fb608c4760446`, a
disposable pgvector PostgreSQL service, and both Spine migrations. At test
composition only, mount a Harness-owned app factory that supplies a closed set
of deterministic 1536-dimensional embeddings through Spine's existing
provider-injection seam. Tear down the database, network, containers, volume,
and locally built image after every run.

**Motivation.** Exact status-correlated decoding keeps API drift visible to the
daemon instead of letting structurally similar success and conflict bodies pass
under the wrong semantics. Exercising the public client against a migrated,
real HTTP and pgvector stack proves the cross-repository boundary without cloud
credentials, external model calls, or changes to Spine production code.

**Rejected alternatives.** Mock-only tests cannot detect routing, migration,
serialization, or container-startup drift. Following a mutable Spine branch
would make Harness CI change without a Harness commit. A generated client adds
another build artifact without reducing this seven-route surface. Retrying
mutations risks duplicate decisions, while following redirects could send the
bearer token outside the configured service. Calling OpenAI or the deployed
cloud service would make routine verification depend on credentials, quota,
cost, and mutable external state; adding a fake provider to Spine production
would widen that repository solely for this packet.
