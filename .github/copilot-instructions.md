# AI-PaaS Repository Working Instructions

## Current formal architecture

This repository has two zones:

- **formal mainline**: the only area that should be extended
- **archived legacy area**: historical material kept only for reference and governance

## Formal mainline

Use and extend only these areas:

- `gateway/`
  - formal HTTP/API surface
  - main public endpoints:
    - `POST /api/v1/agent/run`
    - `POST /api/v1/agent/submit`
    - `POST /api/v1/generation/image`
    - `POST /api/v1/generation/image/submit`
    - `POST /api/v1/generation/video`
    - `POST /api/v1/generation/video/submit`
    - `GET /api/v1/tasks/{task_id}`
    - `GET /api/health`

- `runtime/`
  - task models
  - queue layer
  - workers
  - runtime execution services

- `control_plane/`
  - formal control-plane services such as registry, repositories, and buses that are still used by the mainline

- `data_plane/`
  - only the surviving formal infrastructure still referenced by the mainline

- `bootstrap/`
  - formal runtime assembly/bootstrap logic

- `webapp/`
  - formal frontend
  - start with Vite dev server on port `5173`

- root startup scripts
  - `run_ai_platform_v4.sh`
  - `start_frontend.sh`
  - `start_infra.sh`
  - `start_core_services.sh` when applicable to current mainline flow

## Archive policy

Anything under `archive/legacy/` is historical only.

Rules:

1. Do not import code from archived paths into the formal mainline.
2. Do not restore archived files back to formal paths.
3. Do not treat archived notes, docs, scripts, or snapshots as current architecture.
4. If historical behavior must be understood, read archive material only as reference, then implement against the formal mainline above.

## Working rules for contributors

When changing the repository:

1. Prefer `gateway/`, `runtime/`, `control_plane/`, `bootstrap/`, `webapp/`, and active root scripts.
2. Keep tests under:
   - `tests/gateway/`
   - `tests/runtime/`
   - `tests/governance/`
3. Keep governance protections passing.
   - baseline governance command: `pytest tests/governance -q`
   - baseline runtime/gateway command: `pytest tests/runtime tests/gateway -q`
4. If a historical artifact is discovered outside `archive/legacy/`, archive it instead of building on top of it.

## Frontend convention

The formal frontend is the Vite app in `webapp/`.

- Dev URL: `http://localhost:5173`
- `start_frontend.sh` should target the Vite webapp flow
- Do not describe Docker Flowise as the formal frontend

## Runtime convention

The formal runtime is:

Gateway API -> Task Submission Service -> Task Store / Outbox -> Redis Queue -> Runtime Workers

Operationally, the mainline also supports synchronous execution paths exposed by the formal gateway/runtime surface.

Mainline work should align to that path and not to historical implementations.

## If unsure

If a file appears historical, check whether it is already under `archive/legacy/`.
If not, prefer governance cleanup rather than compatibility layering.
