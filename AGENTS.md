# AI-PAAS Repository Instructions

## Language
- 所有解释、分析、总结使用中文
- API schema 保持英文
- 代码注释优先中文

## Architecture Rules
- 不允许绕过 durable runtime mainline
- 不允许新增 compatibility layer
- 所有 workflow 必须走 canonical schema
- gateway.main:app 是 control plane
- main:app 是 runtime plane

## Engineering Rules
- 不允许为了通过测试修改测试逻辑
- 优先 root-cause fix
- 修改前先分析影响范围
- 输出完整文件路径
- 避免 mock-based fixes

## Runtime Principles
- Redis Streams 是 canonical queue
- Postgres outbox 是 durable source of truth
- Workflow execution 必须可恢复
