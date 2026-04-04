AI OS Workflow 功能总表（按当前理解与现状整理）
层级	功能点名称	功能描述	对外调用方式	对内执行方式	关键数据/对象	当前状态	已验证情况	后续重点
产品层	Workflow Product 封装	把内部 workflow 封装成对外可调用产品，用户不直接接触 node graph	POST /api/v1/workflow/products	保存 product definition，并绑定内部 workflow	workflow_products	已开发	已通过 create API 测试	后续补版本治理、权限控制
产品层	Product 提交执行	用户按产品合同提交执行请求，不暴露内部节点配置	POST /api/v1/workflow/products/submit	生成 workflow 类型 task，进入 durable submit 主线	runtime_tasks, runtime_outbox_events	已开发	已通过 gateway + durable integration	后续补 submit 校验、配额、审计
产品层	Public API Schema	定义产品对外输入字段、约束、required 字段	product payload 中 public_api_schema_json	当前存储为 JSON schema，执行前未深度校验	public_api_schema_json	已开发（存储）	已通过 create/update 存储链路	后续补正式 schema validation
产品层	UI Schema	定义前端表单渲染方式，不暴露内部 capability 配置	product payload 中 ui_schema_json	仅作为元数据存储，不影响 runtime	ui_schema_json	已开发（存储）	已通过 create/update 存储链路	后续补前端消费与表单生成
产品层	Execution Binding	将 product 绑定到内部 workflow_key/workflow_version	product payload 中 execution_binding	submit 时解析 product -> workflow	bound_workflow_key, bound_workflow_version	已开发	已通过 submit mainline	后续补 input mapping 与 context merge 增强
产品层	Product 可见性	控制 product 是 tenant/private/public	product payload 中 visibility	当前作为元数据存储	visibility	已开发（存储）	已通过持久化	后续补真正权限判定
产品层	Product 状态管理	draft/active/disabled/deprecated 控制是否允许调用	create/update product	submit 时检查 status	status	已开发	已验证 active/不存在路径	后续补 activate/deprecate 生命周期
定义层	Workflow Definition 持久化	保存 workflow 图定义与版本	POST /api/v1/workflow/definitions	repository 写入 definition	workflow_definitions	已开发	已通过 gateway/repository 测试	后续补版本升级策略
定义层	Active Definition 查询	获取某个 workflow key 当前 active 版本	GET /api/v1/workflow/definitions/{workflow_key}/active	repository 查询 active	workflow_definitions.status	已开发	已通过 gateway 测试	后续补 activate/rollback
定义层	指定版本查询	获取某 workflow 的指定版本定义	GET /api/v1/workflow/definitions/{workflow_key}/{workflow_version}	repository 查询 version	workflow_key,workflow_version	已开发	已通过 gateway 测试	后续补版本 diff
定义层	Workflow 图结构	支持 start/capability/end 基础节点图	definition payload	runtime 解析 node/edge 执行	WorkflowNode,WorkflowEdge	已开发	已通过 success/failure execution	后续补 decision/parallel/subworkflow
定义层	Capability 引用	capability node 引用 agent/skill 等原子能力	definition node 中 capability_ref	由 capability executor 执行	CapabilityRef,CapabilityKind	已开发	已通过 deterministic executor	后续接真实 agent runtime
执行层	Workflow Runtime Service	执行 workflow 的核心状态机	不直接对外	worker 调用 WorkflowRuntimeService.run(task)	workflow_runtime_service.py	已开发	success/failure mainline 已验证	后续补 retry/decision/多 step
执行层	Workflow Worker	消费 workflow_tasks 队列并执行 task	不直接对外	Redis Streams -> worker -> runtime service	workflow_worker.py	已开发	已通过异步执行 success/failure 集成测试	后续补并发控制与 worker metrics
执行层	顺序单 step 执行	当前支持 start -> capability -> end 的顺序执行闭环	通过 product submit 或 workflow submit 间接触发	runtime 顺序推进 active node	execution/step/event 表	已开发	已通过 success/failure 集成测试	后续扩展为多 step 顺序链
执行层	Deterministic Capability Executor	先用稳定的 deterministic executor 保证状态机正确	不直接对外	capability executor 返回 success 或按条件注入 failure	capability_executor.py	已开发	已通过 success/failure 注入验证	后续切换真实 agent runtime adapter
执行层	失败注入	用 force_fail_node_id 等方式触发确定性失败	submit input_json 中透传	executor 检查节点或 metadata 注入失败	input/context/metadata	已开发	已通过 failure mainline	后续用于 retry/mainline 测试
执行层	Execution 创建	每次 workflow 运行生成 execution 记录	不直接对外	runtime 创建 execution	workflow_executions	已开发	已通过 success/failure 集成测试	后续补 parent/child/subworkflow
执行层	Step Execution 创建	每个 capability node 生成 step execution	不直接对外	runtime 创建/更新 step	workflow_step_executions	已开发	已通过 success/failure 集成测试	后续补 attempt_no、retry history
执行层	Execution Event 记录	execution.created / running / succeeded / failed 等事件	不直接对外	runtime 按状态迁移写 event	workflow_execution_events	已开发	已通过 success/failure 集成测试	后续补 retrying/decision taken/parallel join
执行层	Task 终态回写	workflow 执行结果最终回写到 runtime task	GET /api/v1/tasks/{task_id} 查询	worker 统一把 task 置 succeeded/failed	runtime_tasks.status	已开发	已通过轮询 task 状态验证	后续补 cancel/timeout
查询层	Execution by Task 查询	可根据 task_id 查询关联 execution	GET /api/v1/workflow/executions/by-task/{task_id}	repository 按 task_id 查 execution	workflow_executions.task_id	已开发	已通过 gateway/repo 测试	后续补 product submit 返回 execution_id
查询层	Execution Detail 查询	查询 execution 详情	GET /api/v1/workflow/executions/{workflow_execution_id}	repository 汇总 execution 详情	execution / step / event	已开发	已通过 gateway 测试	后续补完整 execution timeline API
持久化层	Workflow Definitions 表	保存 workflow 定义与版本	不直接对外	repository CRUD	workflow_definitions	已开发	已通过 Postgres/repository 测试	后续补 schema checksum/activation rules
持久化层	Workflow Executions 表	保存每次 workflow 运行	不直接对外	runtime 写 execution	workflow_executions	已开发	已通过 success/failure	后续补 indexes / correlation 查询
持久化层	Workflow Step Executions 表	保存每个 step 执行状态	不直接对外	runtime 写 step 状态	workflow_step_executions	已开发	已通过 success/failure	后续补 retry attempt model
持久化层	Workflow Execution Events 表	保存事件轨迹	不直接对外	runtime 写 event log	workflow_execution_events	已开发	已通过 success/failure	后续补 richer event payload
持久化层	Workflow Products 表	保存产品层定义与绑定关系	POST /workflow/products	repository upsert/query	workflow_products	已开发	已通过 gateway/durable 测试	后续补 tenant 隔离与索引优化
Durable 主线	Task Submission Service 接入	workflow product submit 正式接入 durable mainline	POST /workflow/products/submit	TaskSubmissionService 事务写 task+outbox	runtime_tasks,runtime_outbox_events	已开发	已通过 durable submit integration	后续补 quota / policy hooks
Durable 主线	Outbox Relay	把 outbox 事件发布到 Redis Streams	不直接对外	relay 扫描 runtime_outbox_events -> publish	outbox relay runner	已开发	已通过 product execution success/failure 测试	后续补 backoff / DLQ / observability
Durable 主线	Redis Workflow Queue	workflow task 的实际异步传输通道	不直接对外	Redis Streams workflow_tasks	Redis stream/group	已开发	已通过 execution mainline	后续补 queue metrics / lag monitor
Runtime 语义	Success Path	capability 成功 -> step succeeded -> execution succeeded -> task succeeded	间接通过 submit 触发	runtime 状态机推进	task/execution/step/event	已开发	已通过完整 success mainline	后续补多 step success
Runtime 语义	Failure Path	capability 失败 -> step failed -> execution failed -> task failed	间接通过 submit + fail injection	runtime/worker 失败传播	task/execution/step/event	已开发	已通过完整 failure mainline	后续补 retry exhausted path
Runtime 语义	Retry Policy 字段	数据模型中已有 retry 方向入口	definition/policy 中可保留	当前未真正驱动状态机	attempt_no, retry_policy_json 相关语义	已有设计入口，未完成	尚未完整验证	下一优先级最高：Retry Mainline
Runtime 语义	Attempt No	为 retry 留出的 attempt 次数语义	不直接对外	当前未形成正式 attempt 递增执行	step / runtime state	已有方向，未完成	未验证	随 retry 一起完成
Runtime 语义	step.retrying Event	节点失败后进入重试态的事件	不直接对外	当前未实现正式写入	execution events	待开发	未验证	Retry Mainline 核心
Runtime 语义	多 step 顺序链	支持 2~N 个 capability 节点顺序执行	workflow definition	runtime 按拓扑推进多个 step	execution frontier / step outputs	部分基础已有，未完成	当前只完整验证了单 capability 主链	Retry 后的下一优先级
Runtime 语义	Step Output -> Next Input	前一节点输出作为后一节点输入	definition/runtime 内部机制	需要 runtime 显式传播 outputs	step_outputs/input merge	待扩展	未做正式多 step 验证	多 step 顺序链时完成
Runtime 语义	Decision Node	条件分支选择不同后续 edge	workflow definition 中定义 decision node	runtime 判断条件选择边	node type / edge condition	待开发	未验证	多 step 后再做
Runtime 语义	Parallel / Join	多分支并行执行与汇合	workflow definition	runtime 管理 active frontier / join	active_node_ids / join state	待开发	未验证	decision 稳定后
Runtime 语义	Subworkflow	节点内部调用另一个 workflow	workflow definition	runtime 嵌套 execution/parent-child	parent/child execution relation	待开发	未验证	中后期
Runtime 语义	Timeout Policy	节点/执行超时控制	definition/policy	worker/runtime 识别 timeout	timeout metadata	待开发	未验证	retry 之后
Runtime 语义	Cancel / Abort	运行中任务取消	task/execution control API	worker/runtime 响应 cancel	task/execution state	待开发	未验证	后续治理能力
适配层	真实 Agent Runtime 对接	capability node 真正调 agent/skill/tool runtime，而不是 deterministic executor	间接通过 workflow 执行	capability executor adapter 调真实 runtime	agent runtime adapter	待开发	未验证	高优先级，但在 retry/多 step 之后
适配层	Skill / Tool / Generation 节点统一适配	不同能力节点走统一 contract	workflow definition capability kind	executor 根据 kind 调不同 adapter	capability kind mapping	待开发	未验证	真实 runtime 接入时完成
治理层	Tenant 隔离	product / workflow / execution 都按 tenant 隔离	API 请求 tenant_id	repository/query/filter	tenant_id	部分已有	提交链已有 tenant_id	后续补 product 查询与治理一致性
治理层	ABAC / 权限控制	不同角色对 workflow product / definition / execution 的权限	API 层鉴权	OPA / ABAC policy	user_ctx/tenant_ctx/policy	待开发到 workflow 域	未验证	产品化后必须补
治理层	审计日志	谁创建了 product/definition，谁触发了 execution	create/update/submit 请求	metadata / audit pipeline	created_by/updated_by/operator	部分字段已有	未形成正式审计链	后续必须补
治理层	配额/限流	限制某 tenant/product 的 submit 频率与资源消耗	submit API	pre-submit policy/check	quota metadata	待开发	未验证	商业化前需要
产品化层	Product Version Lifecycle	product 的 activate/deprecate/rollback	product API 扩展	repository + policy	product status/version	部分基础已有	只验证 active submit	后续补完整生命周期
产品化层	Product Catalog / Registry	工作流产品目录、可搜索、可展示	catalog API / UI	registry/repository	product metadata	待开发	未验证	marketplace 前置
产品化层	Product Template	可复用行业模板	product/workflow 定义模板化	template compiler	template defs	待开发	未验证	后续商业化能力
协议层	通用 Workflow 协议抽象	内部使用通用 graph/node/edge/capability 模型，为 BPMN/Flowise/ComfyUI 风格兼容留口	definition model	compiler/runtime consume graph	workflow models	已有基础抽象	当前已用于顺序 capability 流	后续补 decision/parallel/BPMN mapping
协议层	BPMN 映射	Workflow 与 BPMN 的导入/导出/对齐	BPMN import/export API	compiler/mapper	BPMN mapping layer	待开发	未验证	中后期，不是当前优先级
协议层	Public Contract -> Executable Graph Compiler	外部产品合同编译成内部可执行 graph	product create/update 或 compile API	compiler 生成 executable workflow	compiler module	已有设计方向，未完整完成	当前更多是静态 binding，不是完整 compile pipeline	后续增强重点
可观测层	Execution Timeline	展示 execution / step / event 时间线	execution detail API / UI	读 execution/step/event	query layer	部分已有数据基础	详情 API 有基础	后续补专门 timeline 视图
可观测层	Metrics / Monitoring	队列积压、执行耗时、失败率、重试次数	metrics endpoint / monitoring	runtime/worker/relay metrics	metrics system	待开发	未验证	上线前必须补
可观测层	Trace / Correlation	correlation_id 串联 product submit -> task -> execution	submit API	metadata/task/execution 透传	correlation_id	部分已有	durable submit 已透传 correlation_id	后续补全链路 trace 查询
前端层	Product Form Rendering	按 ui_schema/public_api_schema 生成前端表单	webapp 调 product metadata API	前端渲染引擎	ui schema	待开发	未验证	产品化对外时需要
前端层	Workflow Designer	类似 Flowise/ComfyUI 的内部编排界面	内部管理台	designer -> workflow definition	graph editor	待开发	未验证	不是当前优先级
前端层	Execution Console	查看 execution、step、event、日志	webapp API	execution query API	execution views	待开发	未验证	后续运维必需