# AI-PaaS Copilot Instructions

## Architecture Overview

This is a **multi-tenant AI PaaS platform** with three-plane architecture:

### Data Flow Pipeline
```
Client Request → Control Plane (Policy Engine) → Data Plane (Dispatcher/Router) → Execution (Agent/Model/PromptFlow)
```

### Three Core Planes

1. **Control Plane** (`control_plane/`)
   - **Policy Engine** (`policy_engine.py`): ABAC-based authorization using `PolicyContext` (tenant/subject/resource/action/environment)
   - **Prompt Execution Gateway** (`prompt_execution_gateway.py`): Policy enforcement point (PEP)
   - Freezes execution envelopes with all policy decisions before handing to Data Plane
   - Never modifies envelopes once created

2. **Data Plane** (`data_plane/`)
   - **Dispatcher** (`dispatcher.py`): Routes `ExecutionEnvelope` to handlers (agent/model/promptflow)
   - **Router** (`router.py`): Splits requests by `target_type` field
   - Handlers: `agent_handler.py`, `model_handler.py`, `promptflow_handler.py`
   - **Critical**: Data Plane is read-only—never modifies envelopes

3. **Agent Core** (`agent_core/`)
   - **MessageBus** (`envelope_bus.py`): In-memory pub/sub with request/response support
   - **MemoryManager** (`memory.py`): Multi-tenant/session-isolated memory (conversation history, task results)
   - **ReasoningEngine** (`reasoning.py`): Model selection and prompt enhancement
   - **SkillRegistry** (`skills/base_skills.py`): Extensible skill execution framework

### Central Data Structure: ExecutionEnvelope
All requests flow through frozen `ExecutionEnvelope` (defined in `data_plane/envelope.py`):
```python
ExecutionEnvelope(
    envelope_id, request_id, tenant_id,
    subject, action, resource, environment,  # ABAC fields
    target_type, target,  # "agent"/"model"/"promptflow"
    payload,  # execution input
    context  # read-only metadata
)
```

## Service Architecture

### gRPC-Based Services (`services/server/`)
- **AgentService** (`agent_service.py`): Processes agent.task.* topics
- **ModelService** (`model_service.py`): Integrates with LLMs (DeepSeek, Qwen)
- **TaskManager** (`task_manager.py`): Manages task lifecycle
- **AgentRegistry** (`agent_registry.py`): Tracks active agents

### Message Streams (Redis)
```
agent.tasks.stream         → Input tasks from clients
agent.routed.tasks.stream  → After router_bridge dispatch
agent.result.stream        → Completed task results
```

## Critical Patterns & Conventions

### 1. **Multi-Tenancy Isolation**
- All operations accept `tenant_id` and `session_id`
- Memory buckets: `_store[tenant_id][session_id]` (see `agent_core/memory.py`)
- Never assume default tenant in production code

### 2. **Message Format Standardization**
Messages must include StandardMetadata fields:
```python
{
    "request_id": str,
    "envelope_id": str,
    "tenant_id": str,
    "timestamp": str,
    "correlation_id": str,
    "session_id": str
}
```

### 3. **Async/Await Convention**
- All I/O operations are async (database, gRPC, message bus)
- Use `await self.bus.publish()` not `.publish()`
- Chain with `asyncio` and `await` at all levels

### 4. **Error Handling Pattern**
```python
try:
    result = await handler(envelope)
except Exception as e:
    logger.exception("descriptive message")
    return ExecutionResult(envelope_id=..., success=False, error=str(e))
```

### 5. **Proto-First Design**
- All service interfaces defined in `proto/` (agent.proto, envelope.proto, etc.)
- Generate SDK: `python generate_grpc_sdk.py`
- Fixes import paths automatically for gRPC modules
- Import pattern: `from aios_sdk import Agent, Task` (flat structure)

## Developer Workflows

### Build/Regenerate gRPC SDK
```bash
python generate_grpc_sdk.py  # Regenerates _pb2.py/_pb2_grpc.py files
```

### Start Platform
```bash
./run_ai_platform.sh start   # Launches Redis bus, LangGraph, router_bridge, agent system
```

### Test Services
```bash
python aios_sdk/example_usage.py          # SDK usage demo
python aios_sdk/aios_platform_test.py     # Integration tests
```

### Check Message Streams
```bash
redis-cli keys "*stream*"                 # List all streams
redis-cli xrange agent.tasks.stream - +   # View task messages
redis-cli xrange agent.result.stream - +  # View results
```

## Integration Points

### Adding New Service Handler
1. Extend `data_plane/handlers/` with `XyzHandler(BaseHandler)`
2. Register in dispatcher: `dispatcher.register_handler("xyz.action", handler)`
3. Add proto definition to `proto/xyz.proto`
4. Regenerate SDK: `python generate_grpc_sdk.py`

### Adding Agent Skills
1. Create in `agent_core/skills/` extending `BaseSkill`
2. Register via `SkillRegistry.register(skill_name, handler_func)`
3. Called by `ReasoningEngine` after task planning

### Extending Policy Rules
1. Add `PolicyRule` instances to `control_plane/policy_engine.py`
2. Conditions matched using ABAC context paths (e.g., `"tenant.plan_tier"`)
3. Return `PolicyDecision(allow=True/False, obligations={...})`

## Key Files Reference

| File | Purpose |
|------|---------|
| `data_plane/dispatcher.py` | Main execution router |
| `data_plane/envelope.py` | ExecutionEnvelope definition |
| `agent_core/memory.py` | Tenant/session memory isolation |
| `agent_core/envelope_bus.py` | Message pub/sub with correlation |
| `control_plane/policy_engine.py` | ABAC authorization engine |
| `services/server/agent_service.py` | Agent task processor |
| `proto/envelope.proto` | StandardMetadata definition |

## Common Gotchas

- **Don't modify ExecutionEnvelope**: It's frozen (immutable)—wrap payload in ExecutionResult instead
- **Memory scope matters**: Always pass `tenant_id` and `session_id` to avoid cross-tenant leaks
- **Async all the way**: Sync calls in message handlers cause deadlock
- **Proto changes require SDK regeneration**: Update .proto files, then run `generate_grpc_sdk.py`
