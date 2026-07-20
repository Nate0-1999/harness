# H2 Spine client and live-contract evidence

This is builder evidence for packet H2, not the independent M1 verdict reserved
by SPEC B.6. H2 implements the C.4 client boundary and an always-on S1–S2 live
contract job. It adds no agent, memory-tool, gate, panel, or cloud behavior.

## Reproducible gates

From the Harness repository root:

```sh
uv lock --check
PYTHONPATH=src uv run ruff check .
PYTHONPATH=src uv run ruff format --check src tests
.githooks/pre-commit --all
PYTHONPATH=src uv run pytest -m 'not contract' -q
PYTHONPATH=src uv run pytest -q tests/test_spine_client.py tests/test_spine_transport.py
sh tests/contract/run.sh
npm run lint --prefix web
npm run build --prefix web
git diff --check
```

The contract runner defaults `SPINE_SOURCE_DIR` to the sibling `spine`
checkout. CI instead checks out exact Spine commit
`9c51c992b6103ee7492961bcb27fb608c4760446` and passes that absolute directory
to the same runner.

From the Spine repository root, inherited ground was re-verified with:

```sh
TESTCONTAINERS_RYUK_DISABLED=true PYTHONPATH=src uv run --extra dev pytest -q
```

## Recorded result — 2026-07-20

- Harness non-contract suite: `87 passed, 2 deselected in 0.34s`.
- Focused client/model suite: `51 passed in 0.08s`.
- Fresh live Spine contract stack: `2 passed in 4.02s`.
- Spine suite against disposable pgvector PostgreSQL: `158 passed in 5.14s`.
- Ruff lint and format, uv lock, M1 scope fence, shell syntax, workflow YAML,
  Compose resolution, diff whitespace, web ESLint, TypeScript, and the
  production Vite build all passed. The web build transformed 17 modules.

The live run built Spine's production Dockerfile, started fresh
`pgvector/pgvector:pg16`, waited for PostgreSQL, applied Alembic migrations
0001 and 0002, then served Uvicorn over real loopback HTTP. Its cleanup removed
the Spine and PostgreSQL containers, Compose network, anonymous database
volume, and locally built image; a post-run Docker inventory contained no
`harness-h2` artifact.

## What the checks prove

- all seven C.4 operations send their exact method and relative route beneath
  a base URL (including a path prefix), bearer header, JSON body, and query
  parameters, omitting optional nulls;
- the client correlates create's 201-created and 200-similar bodies by status,
  validates every success body and media type, and refuses redirects, malformed
  JSON, wrong schemas, unexpected statuses, and mismatched RFC7807 status;
- create label/duplicate 409s and PATCH label/revision 409s are distinct typed
  domain failures, while `application/problem+json` remains a typed RFC7807
  failure with extension members and the raw response available for inspection;
- transport failures preserve their original exception as the cause, owned
  transports close with the client, and exception text copies neither bearer
  credentials nor response bodies;
- the Harness mirror carries required-nullable `MemoryUnit.origin_path`, the
  optional create/PATCH field, positive prepare context, bounded list paging,
  and strict search `k` exactly as current law and Spine require; and
- through the public `SpineClient`, the live stack proves create, active-label
  conflict, hard-duplicate conflict even with force, the similar band and force
  retry, PATCH re-embedding, stale-revision CAS conflict, tombstoning, active
  label reuse, case-insensitive list filtering, status filtering, and paging.

The mounted contract app supplies only six closed-set deterministic
1536-dimensional vectors through Spine's already-existing provider injection
seam. No Spine source is modified, no production fake is shipped, and the run
makes no OpenAI, model-provider, deployed-cloud, or credential-dependent call.

Three independent read-only audits covered literal C.4 parity, adversarial
transport behavior, and live-stack/CI isolation. Their initial concrete
findings—unsafe base-URL forms, coercive/non-standard JSON acceptance, narrow
request-error wrapping, and an implementation-specific narrowing of optional
RFC7807 members—were fixed and regression-tested. Final re-audits reported no
blocker. The pinned source keeps application behavior stable, but the
production Dockerfile's base image/dependency ranges and the pgvector tag are
not digest-locked; H2 does not claim bit-for-bit build reproducibility.
