# Model / Generation 模块设计文档

## 1. 文档目的

本文档用于定义平台 Model / Generation 模块的职责、边界、内部结构、组装关系、设计原则与后续演进重点。

Model / Generation 模块是平台的模型能力基础设施层，负责为 Agent、Workflow、Generation 等执行面提供统一模型抽象，而不是独立的产品主叙事。

---

## 2. 模块定位

Model / Generation 模块负责：

- 统一模型注册
- 统一模型服务
- 统一 LLM adapter 抽象
- 统一 generation service
- 为 Agent Runtime 与 Generation API 提供底层模型能力
- 为后续多模型、多模态、多租户模型治理提供扩展基础

这一层的目标不是“多接几个模型”，而是把模型能力从平台业务执行逻辑中解耦出来。

---

## 3. 模块边界

### 3.1 模块负责

Model / Generation 模块负责以下能力：

- 模型注册与 provider 抽象
- 模型调用统一服务
- LLM 统一适配层
- generation 执行承接
- 为 runtime 提供统一模型访问接口
- 为未来多模态扩展提供基础结构

### 3.2 模块不负责

该模块不应承担以下职责：

- 对外 API 门户
- workflow 业务编排
- durable task 主链路
- 多租户产品控制台
- 直接替代 runtime 执行层
- 在不同业务路径中重复暴露不同 provider 语义

---

## 4. 当前代码映射

### 4.1 Bootstrap 组装层

当前存在：

```text
bootstrap/
└─ model_bootstrap.py

这说明模型层已经被明确设计为可独立组装的模块，而不是散落在运行时中的零散逻辑。

4.2 Runtime 模型与生成层

当前存在：

runtime/
├─ generation_service.py
├─ model_service.py
├─ llm_adapter.py
├─ model_backed_llm_adapter.py
└─ models/

这表明模型与生成能力已经具备清晰的代码落点。

5. 当前模块结构说明
5.1 model_service.py

职责：

提供统一模型访问服务
为上层执行器屏蔽 provider 差异
承担模型调用逻辑的统一入口
5.2 llm_adapter.py

职责：

定义统一 LLM 抽象
避免 Agent Runtime 等上层模块直接耦合具体模型供应方
5.3 model_backed_llm_adapter.py

职责：

将模型服务转化为上层 runtime 可直接使用的 LLM adapter
构建 model plane 与 runtime plane 之间的桥梁
5.4 generation_service.py

职责：

承接图像、视频等 generation 任务
为 generation API 提供执行面支撑
统一 generation 相关模型调用路径
5.5 runtime/models/

职责：

存放模型定义、provider 适配、模型层细分实现
构成模型平面的扩展区域
6. Bootstrap 组装关系

从当前结构看，bootstrap/model_bootstrap.py 的职责是把模型层组装成可被平台正式使用的能力面。

组装关系可以抽象为：

build model registry
build model service
build model-backed LLM adapter

这说明模型层已经具备以下工程方向：

模块可独立装配
依赖关系相对清晰
与 runtime 执行层通过抽象对接，而不是散乱耦合
7. 模块工程图
flowchart LR
    Config[Model Config] --> Registry[Model Registry]
    Registry --> Service[Model Service]
    Service --> MBA[Model-backed LLM Adapter]
    MBA --> AgentRuntime[Agent Runtime]
    Service --> GenerationService[Generation Service]
    Registry --> Providers[Providers / Adapters]

8. 与平台主线的关系

Model / Generation 模块位于平台主线的后段基础设施层：

Gateway → Durable Task Submission → Queue / Worker → Runtime Capability Execution → Model / Generation Plane

这意味着：

模型层不是接入层
模型层不是 durable task 主线
模型层是 Runtime 执行最终依赖的基础设施能力
上层必须通过统一抽象访问模型层，而不是直接拼接 provider 细节
9. 与其他模块的关系
9.1 与 Runtime 的关系

Runtime 使用 Model / Generation 模块，但不应与单一 provider 强绑定。
Model / Generation 模块为 Runtime 提供稳定抽象。

9.2 与 Gateway 的关系

Gateway 暴露 generation API 和 runtime API，但不负责实际模型调用。
模型调用逻辑应留在 Model / Generation 模块和 Runtime 侧。

9.3 与 Workflow 的关系

Workflow 节点最终可能触发 Agent / Generation / Tool 能力。
其中涉及模型推理或生成的部分，应统一落到 Model / Generation 模块，而不是 workflow 自己再造一层模型访问逻辑。

10. 设计原则
原则 1：模型接入必须统一抽象

不能在 Agent、Workflow、Generation 各自直接耦合不同 provider。

原则 2：Generation 与 Agent 共用模型平面

避免出现：

agent 一套模型调用方式
generation 一套模型调用方式
workflow 又一套模型调用方式
原则 3：provider 可替换，但上层契约尽量稳定

平台价值不应绑死在单一模型厂商上。
模型层存在的意义，就是让上层平台能力在 provider 更替时保持相对稳定。

原则 4：模型层是基础设施，不是产品主叙事

平台对外的核心价值是 AI capability orchestration 与治理，不是“支持多少模型”。

原则 5：模型层应支持平台级治理扩展

未来模型层不只是“调用成功”，还需要逐步承接：

配额
成本
provider routing
fallback
tenant-level config
model policy
observability
11. 当前已实现能力

当前 Model / Generation 模块已具备以下基础能力：

Model bootstrap
Model service
LLM adapter
Model-backed LLM adapter
Generation service
模型子目录结构
为 runtime 提供统一模型执行抽象

这表明平台已经具备“模型平面”的初步结构，而不是散点式模型调用。

12. 当前工程判断
12.1 模型层已经具备模块化基础

这是平台长期可扩展的重要前提。
如果没有统一模型平面，后续 provider 增加会迅速导致运行时执行层耦合失控。

12.2 当前仍需进一步固化 provider 抽象边界

未来平台支持的模型种类、模态、供应商会越来越多。
如果抽象边界不稳定，上层 Runtime 与 Workflow 将被 provider 差异污染。

12.3 当前需要防止“generation 独立膨胀为第二套模型系统”

Generation 当然有自身特点，但仍应建立在统一模型平面之上，而不是脱离整体架构另建系统。

13. 后续演进重点
13.1 明确 provider 适配层边界

需要进一步规范：

provider interface
model metadata
provider config
error mapping
retry / timeout strategy
capability declaration
13.2 明确 generation modality 扩展策略

后续 generation 不应局限于图像/视频，还应考虑：

audio
multimodal input
multimodal output
structured generation
13.3 明确模型配置与租户配置关系

需要支持：

global model config
tenant override
model allowlist / denylist
tenant-specific quotas
tenant-specific routing policy
13.4 明确模型调用可观测性

模型层应逐步支持：

trace
latency
token / usage stats
cost estimation
provider fallback records
error classification
13.5 补齐多模型治理文档

后续需要将模型平面进一步文档化，包括：

model registry 设计
provider adapter 设计
routing / fallback 设计
quota / cost control 设计
14. 模块总结

Model / Generation 模块是平台的“模型能力基础设施层”。

它的价值不在于把模型能力变成平台主角，而在于让平台上层：

Agent
Workflow
Generation
Governance

都能建立在一个统一、可替换、可扩展的模型平面之上。

因此，该模块必须始终坚持：

provider 解耦
统一模型抽象
runtime 与 generation 共用底层平面
为治理与多租户扩展预留接口
不把模型层膨胀成新的产品主叙事

只有这样，平台才能在模型生态快速变化的情况下，保持架构稳定和产品连续性。