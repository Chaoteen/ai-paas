#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Optional

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

SOURCE_STREAM = os.getenv("SOURCE_STREAM", "agent.tasks.stream")
RESULT_STREAM = os.getenv("RESULT_STREAM", "agent.result.stream")

WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", "30"))

def now() -> float:
    return time.time()

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"

def build_control_plane_envelope(
    tenant_id: str,
    user_id: str,
    content: str,
    task_type: str,
    model: str = "",
) -> Dict[str, Any]:
    request_id = new_id("req")
    envelope_id = new_id("env")
    session_id = new_id(f"sess_{tenant_id}")
    task_id = new_id("task")

    data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": session_id,
        "task_id": task_id,
        "message_seq": 0,

        "content": content,
        "task_type": task_type,
        "model": model,

        "role": "tester",
        "permissions": ["default_access"],
        "timestamp": now(),
    }

    envelope = {
        "topic": "agent.tasks",
        "data": data,
        "timestamp": now(),
        "message_id": str(uuid.uuid4()),

        "tenant_id": tenant_id,
        "request_id": request_id,
        "envelope_id": envelope_id,
        "session_id": session_id,
        "task_id": task_id,
    }
    return envelope

def xadd_json(r: redis.Redis, stream: str, obj: Dict[str, Any]) -> str:
    payload = json.dumps(obj, ensure_ascii=False)
    return r.xadd(stream, {"message": payload}, maxlen=10000)

def wait_result_by_request_id(
    r: redis.Redis,
    request_id: str,
    timeout_s: int = WAIT_TIMEOUT,
) -> Optional[Dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_id = "0-0"  # 避免用 "$" 导致漏读
    while time.time() < deadline:
        resp = r.xread({RESULT_STREAM: last_id}, block=2000, count=10)
        if not resp:
            continue
        for _stream_name, msgs in resp:
            for msg_id, fields in msgs:
                last_id = msg_id
                raw = fields.get("message")
                if not raw:
                    continue
                try:
                    env = json.loads(raw)
                except Exception:
                    continue
                if env.get("request_id") == request_id:
                    return env
    return None

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    tests = [
        build_control_plane_envelope(
            tenant_id="tenant_a",
            user_id="u_1001",
            content="请分析市场数据并生成一份简报（包含要点和建议）",
            task_type="analysis",
            model="",
        ),
        build_control_plane_envelope(
            tenant_id="tenant_b",
            user_id="u_2001",
            content="请把下面这段话总结成3条要点：公司本季度营收同比增长18%，主要来自海外市场拓展与新产品线发布。研发投入提升到营收的12%，重点在多模态模型与推理加速。与此同时，供应链成本上升导致毛利率下滑1.6个百分点，公司计划通过更换供应商与提升自动化来改善。",
            task_type="summary",
            model="",
        ),
    ]

    print(f"📨 发送 {len(tests)} 条多租户测试任务到 {SOURCE_STREAM} ...")

    tracking = []
    for env in tests:
        mid = xadd_json(r, SOURCE_STREAM, env)
        request_id = env["request_id"]
        print(f"✅ XADD id={mid} tenant={env['tenant_id']} request_id={request_id} task_id={env['task_id']}")
        tracking.append((env["tenant_id"], request_id))

    print("")
    print(f"⏳ 等待结果（stream={RESULT_STREAM}, timeout={WAIT_TIMEOUT}s）...")

    for tenant_id, req_id in tracking:
        res = wait_result_by_request_id(r, req_id, WAIT_TIMEOUT)
        if not res:
            print(f"❌ 超时未收到结果: tenant={tenant_id} request_id={req_id}")
            continue

        print("")
        print("========================================")
        print(f"✅ 收到结果 tenant={tenant_id} request_id={req_id}")
        print(f"   envelope_id={res.get('envelope_id')} session_id={res.get('session_id')} task_id={res.get('task_id')}")
        print(f"   status={res.get('status')} model={res.get('model')} latency_ms={res.get('latency_ms')}")
        print("   output:")
        out = res.get("output")
        if isinstance(out, (dict, list)):
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(out)

if __name__ == "__main__":
    main()
