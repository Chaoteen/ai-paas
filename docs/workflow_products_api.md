# Workflow Products API

## 1. 设计目标

对外暴露的是 workflow product，不是内部 workflow graph。

最终用户和前端只看到：

- product_key
- display_name
- public_api_schema_json
- ui_schema_json

不暴露：

- capability node
- retry_policy
- timeout_policy
- active_node_ids
- 内部 workflow definition 结构

---

## 2. 创建/更新产品

POST /api/v1/workflow/products

### 请求示例

```json
{
  "product": {
    "product_key": "solar_lamp_product_plan",
    "product_version": "1.0.0",
    "display_name": "太阳能庭院灯产品规划助手",
    "status": "active",
    "public_api_schema_json": {
      "type": "object",
      "properties": {
        "target_market": {"type": "string"},
        "cost_target": {"type": "number"},
        "style_direction": {"type": "string"}
      },
      "required": ["target_market", "cost_target"]
    },
    "ui_schema_json": {
      "form": [
        {"field": "target_market", "component": "input"},
        {"field": "cost_target", "component": "number"},
        {"field": "style_direction", "component": "textarea"}
      ]
    },
    "execution_binding": {
      "workflow_key": "solar_lamp_internal_flow",
      "workflow_version": "3.2.0",
      "default_input_json": {},
      "default_context_json": {"channel": "product_api"},
      "input_mapping_json": {}
    },
    "governance_json": {},
    "metadata_json": {"category": "manufacturing"},
    "visibility": "tenant"
  }
}

3. 提交产品执行

POST /api/v1/workflow/products/submit

请求示例
{
  "product_key": "solar_lamp_product_plan",
  "input_json": {
    "target_market": "EU garden retail",
    "cost_target": 12.5,
    "style_direction": "warm ambient minimalism"
  },
  "context_json": {
    "operator": "pm_assistant"
  },
  "metadata_json": {
    "request_channel": "web"
  },
  "trigger_source": "workflow_product_api",
  "idempotency_key": "order-20260325-001",
  "correlation_id": "corr-20260325-001"
}
响应示例
{
  "task_id": "task-xxx",
  "task_type": "workflow",
  "queue_name": "workflow_tasks",
  "status": "queued",
  "bound_workflow_key": "solar_lamp_internal_flow",
  "bound_workflow_version": "3.2.0"
}

---

## 文件 8：新建  
## `tests/gateway/test_workflow_products_api.py`

```python
from fastapi.testclient import TestClient

from gateway.main import app

client = TestClient(app)


def test_create_workflow_product():
    response = client.post(
        "/api/v1/workflow/products",
        json={
            "product": {
                "product_key": "solar_lamp_product_plan",
                "product_version": "1.0.0",
                "display_name": "太阳能庭院灯产品规划助手",
                "status": "active",
                "public_api_schema_json": {
                    "type": "object",
                    "properties": {
                        "target_market": {"type": "string"},
                        "cost_target": {"type": "number"},
                        "style_direction": {"type": "string"},
                    },
                    "required": ["target_market", "cost_target"],
                },
                "ui_schema_json": {
                    "form": [
                        {"field": "target_market", "component": "input"},
                        {"field": "cost_target", "component": "number"},
                        {"field": "style_direction", "component": "textarea"},
                    ]
                },
                "execution_binding": {
                    "workflow_key": "solar_lamp_internal_flow",
                    "workflow_version": "3.2.0",
                    "default_input_json": {},
                    "default_context_json": {"channel": "product_api"},
                    "input_mapping_json": {},
                },
                "governance_json": {},
                "metadata_json": {"category": "manufacturing"},
                "visibility": "tenant",
            }
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["product"]["product_key"] == "solar_lamp_product_plan"
    assert body["product"]["execution_binding"]["workflow_key"] == "solar_lamp_internal_flow"


def test_submit_workflow_product():
    create_resp = client.post(
        "/api/v1/workflow/products",
        json={
            "product": {
                "product_key": "solar_lamp_product_plan",
                "product_version": "1.0.0",
                "display_name": "太阳能庭院灯产品规划助手",
                "status": "active",
                "public_api_schema_json": {
                    "type": "object",
                    "properties": {
                        "target_market": {"type": "string"},
                        "cost_target": {"type": "number"},
                    },
                    "required": ["target_market", "cost_target"],
                },
                "ui_schema_json": {"form": []},
                "execution_binding": {
                    "workflow_key": "solar_lamp_internal_flow",
                    "workflow_version": "3.2.0",
                    "default_input_json": {},
                    "default_context_json": {"channel": "product_api"},
                    "input_mapping_json": {},
                },
                "governance_json": {},
                "metadata_json": {"category": "manufacturing"},
                "visibility": "tenant",
            }
        },
    )
    assert create_resp.status_code == 201

    submit_resp = client.post(
        "/api/v1/workflow/products/submit",
        json={
            "product_key": "solar_lamp_product_plan",
            "input_json": {
                "target_market": "EU garden retail",
                "cost_target": 12.5,
                "style_direction": "warm ambient minimalism",
            },
            "context_json": {
                "operator": "pm_assistant",
            },
            "metadata_json": {
                "request_channel": "web",
            },
            "trigger_source": "workflow_product_api",
            "idempotency_key": "order-20260325-001",
            "correlation_id": "corr-20260325-001",
        },
    )

    assert submit_resp.status_code == 200
    body = submit_resp.json()
    assert body["task_type"] == "workflow"
    assert body["queue_name"] == "workflow_tasks"
    assert body["bound_workflow_key"] == "solar_lamp_internal_flow"
    assert body["bound_workflow_version"] == "3.2.0"