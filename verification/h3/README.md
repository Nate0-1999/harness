# H3 verification — agent and memory tools

H3 implements only the C.5/C.6 agent surface and ADR-013 seam. It does not
wire WebSocket payloads, injection gates, or loop controls; H4, H5, and H7 own
those behaviors.

## Trace

- `src/harness/capability.py` is the frozen Harness-owned capability contract.
- `src/harness/memory_capability.py` contains the exact C.6 instruction and
  three framework-free tool definitions.
- `src/harness/pydantic_ai_adapter.py` is the sole capability-machinery import
  and exports a vanilla pydantic-ai v2 `MemoryCapability`.
- `src/harness/tools_memory.py` maps trusted run context to C.4 requests,
  surfaces create conflicts/similarity, and performs the single edit CAS retry.
- `src/harness/agent.py` provides bounded chat and the tools-free, one-label-call
  `/remember` dispatch service.

## Evidence

Run from `harness/`:

```sh
PYTHONPATH=src uv run pytest -q -m 'not contract'
uv run ruff check .
uv run ruff format --check src tests
.githooks/pre-commit --all
sh tests/contract/run.sh
```

Observed on 2026-07-20:

- 147 passed, 2 contract tests deselected
- Ruff lint and format gates passed
- M1 scope fence passed
- live migrated Spine contract: 2 passed

The 61 focused H3 cases are in `test_memory_capability.py`,
`test_tools_memory.py`, `test_agent.py`, and `test_config.py`. They run with
local pydantic-ai test/function models and fake Spine gateways, so they make no
provider, credential, cloud, or billable calls.

Sibling Spine regression evidence:

```sh
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
  PYTHONPATH=src uv run pytest -q
```

Observed: 158 passed. The socket override is required by this workstation's
Colima context; it changes only how Testcontainers reaches Docker.
