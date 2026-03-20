# AI-PaaS Repository Working Instructions

## Current formal architecture

This repository has a **formal mainline** and an **archived legacy area**.

### Formal mainline
Use and extend these paths:

- `gateway/`
  - Formal HTTP/API entrypoint
  - Main public contract is:
    - `POST /api/v1/agent/run`
    - `POST /api/v1/agent/submit`
    - `POST /api/v1/generation/image`
    - `POST /api/v1/generation/image/submit`
    - `POST /api/v1/generation/video`
    - `POST /api/v1/generation/video/submit`
    - `GET /api/v1/tasks/{task_id}`
    - `GET /api/health`

- `runtime/`
  - Formal runtime execution layer
  - Includes:
    - agent runtime
    - model adapters
    - generation service
    - workers
    - queue integration
    - task store / outbox / idempotency / trace / metrics

- `bootstrap/`
  - Formal startup/bootstrap assembly

- `persistence/`
  - Formal persistence support

- `tests/runtime/`
- `tests/gateway/`
- `tests/governance/`

### Governance rule
Anything under `archive/legacy/` is **not** part of the formal production path.

Rules:

- Do not import from `archive/legacy/`
- Do not restore archived modules into formal paths
- Do not make new production features on top of archived modules
- If legacy behavior is only needed for audit/reference, keep it archived

---

## Current execution mainline

Formal execution path is:

`Gateway API -> Task Submission Service -> Task Store / Outbox -> Redis Queue -> Runtime Workers`

This is the architecture to preserve and extend.

### Formal async flow
- Gateway receives API request
- Submission service validates and persists task
- Outbox records event
- Queue publishes task
- Runtime worker consumes task
- Runtime executes skill/model/generation
- Task status becomes queryable through task API

### Formal sync flow
- Gateway may directly invoke formal runtime services where tests already define that behavior
- Keep all sync behavior aligned with the runtime contracts already covered by `tests/runtime` and `tests/gateway`

---

## What is legacy now

The following historical stacks are archived and must not be treated as active architecture:

- old `agent_core/` runtime stack
- old `services/server/` service runtime stack
- old `control_plane/prompt_execution_gateway.py`
- old `data_plane/router.py`, `router_worker.py`, `agent_worker.py`
- old `data_plane/adapters/` and `data_plane/handlers/`
- old compatibility gateway modules
- old backup scripts and loose operational artifacts

Their copies may still exist under `archive/legacy/` for audit only.

---

## How to extend the platform now

### Adding a new runtime capability
Prefer extending:

- `runtime/`
- `gateway/api/`
- `runtime/models/`
- `runtime/generation/`
- `runtime/tools/`
- `runtime/workers/`
- `runtime/queue/`

### Adding a new API surface
- implement under `gateway/api/`
- wire through formal bootstrap/main entrypoints
- add tests in `tests/gateway/`

### Adding a new runtime behavior
- implement in formal runtime modules
- add tests in `tests/runtime/`
- keep contracts aligned with task submission and worker execution flow

### Persistence changes
- use current persistence / db session factory patterns already present in formal modules
- avoid introducing another historical compatibility path unless explicitly required

---

## Test expectations

Before considering work complete, run:

    pytest tests/governance -q
    pytest tests/runtime tests/gateway -q

Governance must stay green.

Runtime and gateway tests are the required regression baseline.

Notes:

- Some tests intentionally simulate failures and may emit ERROR logs while still passing
- Passing status matters more than the presence of expected negative-path logs

---

## Startup scripts

Current launcher convergence rule:

- `run_ai_platform_v4.sh` is the formal launcher target
- deprecated wrappers may forward to v4
- frozen backup scripts belong to archive/governance inventory, not to active architecture design

---

## Editing policy for contributors

When making changes:

1. Prefer smallest formal-path change
2. Do not reintroduce legacy imports
3. Do not couple new features to archived modules
4. Update governance tests when archive inventory changes
5. Keep documentation consistent with the formal mainline above
