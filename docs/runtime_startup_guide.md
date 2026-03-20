# AI-PaaS Runtime Startup Guide

## Scope

This guide documents the formal Phase 17 runtime mainline startup procedure.

Formal async mainline:

Gateway API  
→ TaskSubmissionService  
→ runtime_tasks / runtime_outbox_events  
→ OutboxRelay  
→ Redis Streams  
→ Runtime Workers  
→ Task Query API

This guide is for local development and runtime validation.

---

## 1. Required infrastructure

The formal runtime mainline requires:

- PostgreSQL
- Redis
- OPA

Minimum local assumptions:

- PostgreSQL on `127.0.0.1:5432`
- Redis on `127.0.0.1:6379`
- database name: `ai_paas`

---

## 2. Required environment variables

### Database

```bash
export TASK_STORE_BACKEND=postgres
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export POSTGRES_DB=ai_paas
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres