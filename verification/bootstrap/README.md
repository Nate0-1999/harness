# P0 Harness Bootstrap Evidence

Observed locally on 2026-07-17 in
`/Users/nateoswalt/Documents/N8_Harness/harness`. This is bootstrap evidence,
not an M1 judge verdict.

## Python scaffold

Command:

```text
uv sync --extra dev
uv run ruff check .
uv run ruff format --check src tests
uv run pytest -q
```

Observed:

```text
All checks passed!
13 files already formatted
s.................. [100%]
18 passed, 1 skipped in 0.13s
```

The single skip is intentional and explicit:
`tests/contract/test_spine_contract.py` reserves the live Spine assertions for
H2. It is not represented as a passing contract test.

## Web scaffold

Command:

```text
cd web
npm ci
npm run lint
npm run build
```

Observed: 153 packages installed from `package-lock.json`, zero npm audit
vulnerabilities, ESLint exited successfully, TypeScript compiled, and Vite
8.1.5 produced `dist/index.html` plus CSS/JS assets from 17 transformed
modules.

## Real developer command, static shell, and WebSocket

Command: `uv run harness dev`.

Observed before the probes below: the command completed `npm ci`, completed
the Vite production build, and started Uvicorn on `127.0.0.1:8765`.

An HTTP request to the running daemon returned:

```text
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8
content-length: 495
<title>Harness
```

A live WebSocket client sent this valid C.7 envelope to `/ws`:

```json
{"v":1,"id":"01ARZ3NDEKTSV4RRFFQ69G5FAV","ts":"2026-07-17T12:00:00Z","machine_id":"machine-1","agent_id":"agent-1","thread_id":"thread-1","type":"prompt.submit","payload":{"prompt":"hello"}}
```

The running daemon returned:

```json
{"agent_id":"agent-1","id":"01ARZ3NDEKTSV4RRFFQ69G5FAV","machine_id":"machine-1","payload":"not implemented","thread_id":"thread-1","ts":"2026-07-17T12:00:00Z","type":"error","v":1}
```

The server was then stopped cleanly.

## Responsive shell — 390×844

The built shell was loaded through the running daemon in the in-app browser
with an explicit 390×844 viewport. The rendered document reported
`innerWidth=390`, `htmlScrollWidth=390`, and `bodyScrollWidth=390`; the shell
occupied exactly 390 CSS pixels with no horizontal overflow. Its accessible
tree exposed the banner, main heading, scaffold notice, and footer, and the
browser console contained no errors.

Screenshot: [`shell-390x844.jpg`](shell-390x844.jpg) (390×844).

## Contract, law, and scope checks

- `docs/SPEC.md` compared byte-for-byte equal to
  `../garden_v1/harness-memory-spec.md`.
- `AGENTS.md` and `CLAUDE.md` compared equal and contain the PLAN §6 relay
  template.
- The C.4 client exposes seven async endpoint stubs; the C.7 enum exposes the
  eight named M1 message types.
- Source/test/web-source grep found no implementation of the B.4 forbidden
  feature families. `agent.py`, `memory_capability.py`, and `tools_memory.py`
  contain module documentation only.
- The tracked pre-commit scope fence passed over the complete repository and
  rejected an isolated staged probe containing a forbidden online-weight
  update marker. The probe was removed from the index after the check.
- `.github/workflows/ci.yml` parsed as YAML. Its separate
  `contract-test-skeleton` targets the configurable `SPINE_CONTRACT_IMAGE`
  service and is skipped when that repository variable is absent. No live
  Spine container contract run is claimed in this evidence.
