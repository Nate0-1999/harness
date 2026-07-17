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
