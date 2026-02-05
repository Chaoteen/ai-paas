#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI-PaaS LangGraph gRPC Routing Server (policy + pipeline router)

Key semantics (IMPORTANT):
- RoutingResponse.target_agent MUST be a real runnable model id (e.g. deepseek-r1:latest)
- "Logical agent / pipeline" is expressed via RoutingResponse.parameters["pipeline_id"]
  e.g. translate_v1 / summarize_v1 / code_v1 / default_v1
- RouterBridge remains thin: it just forwards + writes processed stream
- ModelWorker can keep using target_agent as model name; no more "agent.translate not found"
"""

from __future__ import annotations

import os
import sys
import time
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import grpc
from concurrent import futures

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aios_sdk import langgraph_pb2, langgraph_pb2_grpc  # type: ignore


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PORT = int(os.getenv("LANGGRAPH_PORT", "50051"))

# Real runnable model id (Ollama model name)
DEFAULT_MODEL = os.getenv("DEFAULT_AGENT", "deepseek-r1:latest")

RULES_PATH = os.getenv("ROUTING_RULES_PATH", os.path.join("langgraph", "routing_rules.yaml"))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("langgraph_grpc_server")


def _find_servicer_base() -> type:
    candidates: List[type] = []
    for name in dir(langgraph_pb2_grpc):
        if not name.endswith("Servicer"):
            continue
        obj = getattr(langgraph_pb2_grpc, name)
        if isinstance(obj, type) and hasattr(obj, "GetRoutingDecision"):
            candidates.append(obj)
    if not candidates:
        raise RuntimeError("No *Servicer with GetRoutingDecision found in aios_sdk.langgraph_pb2_grpc")
    candidates.sort(key=lambda c: (("router" not in c.__name__.lower()), c.__name__))
    return candidates[0]


def _find_add_to_server() -> Any:
    fns = []
    for name in dir(langgraph_pb2_grpc):
        if name.startswith("add_") and name.endswith("_to_server"):
            fn = getattr(langgraph_pb2_grpc, name)
            if callable(fn):
                fns.append((name, fn))
    if not fns:
        raise RuntimeError("No add_*_to_server function found in aios_sdk.langgraph_pb2_grpc")
    fns.sort(key=lambda x: (("router" not in x[0].lower()), x[0]))
    return fns[0][1]


ServicerBase = _find_servicer_base()
add_servicer_to_server = _find_add_to_server()


@dataclass
class Rule:
    task_type_in: List[str]
    contains_any: List[str]

    # IMPORTANT:
    # - model: real model id
    # - pipeline_id: logical pipeline (translate/code/summarize/...)
    model: str
    pipeline_id: str
    confidence: float
    strategy: str


def _try_load_yaml(path: str) -> Optional[dict]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _load_rules(path: str) -> Tuple[List[Rule], str]:
    if not os.path.exists(path):
        return [], f"no rules file ({path})"

    data: Optional[dict] = None
    if path.lower().endswith((".yaml", ".yml")):
        data = _try_load_yaml(path)
        if data is None:
            try:
                data = json.loads(open(path, "r", encoding="utf-8").read())
            except Exception as e:
                return [], f"failed to parse yaml/json rules: {e}"
    else:
        try:
            data = json.loads(open(path, "r", encoding="utf-8").read())
        except Exception:
            data = _try_load_yaml(path)

    if not isinstance(data, dict):
        return [], "rules file parsed but not a dict"

    raw_rules = data.get("rules") or []
    if not isinstance(raw_rules, list):
        return [], "rules.rules is not a list"

    rules: List[Rule] = []
    for i, r in enumerate(raw_rules):
        if not isinstance(r, dict):
            continue
        match = r.get("match") or {}
        if not isinstance(match, dict):
            match = {}

        task_type_in = match.get("task_type_in") or []
        contains_any = match.get("contains_any") or []
        if isinstance(task_type_in, str):
            task_type_in = [task_type_in]
        if isinstance(contains_any, str):
            contains_any = [contains_any]

        task_type_in = [str(x).lower() for x in (task_type_in or [])]
        contains_any = [str(x).lower() for x in (contains_any or [])]

        model = str(r.get("model") or DEFAULT_MODEL)
        pipeline_id = str(r.get("pipeline_id") or f"default_v1")
        confidence = float(r.get("confidence") or 0.5)
        strategy = str(r.get("strategy") or f"rule[{i}]")

        rules.append(
            Rule(
                task_type_in=task_type_in,
                contains_any=contains_any,
                model=model,
                pipeline_id=pipeline_id,
                confidence=confidence,
                strategy=strategy,
            )
        )

    return rules, f"loaded {len(rules)} rules from {path}"


class RoutingServicer(ServicerBase):
    def __init__(self):
        self._rules: List[Rule] = []
        self._rules_info: str = ""
        self._load()

    def _load(self):
        self._rules, self._rules_info = _load_rules(RULES_PATH)
        logger.info("📦 routing rules: %s", self._rules_info)

    def _resp(
        self,
        request,
        model: str,
        pipeline_id: str,
        confidence: float,
        strategy: str,
        reason: str,
    ) -> langgraph_pb2.RoutingResponse:
        # parameters is a map<string, string> in pb; keep values as strings
        params: Dict[str, str] = {
            "pipeline_id": pipeline_id,
            "model": model,
            "reason": reason,
        }
        return langgraph_pb2.RoutingResponse(
            target_agent=model,               # MUST be real runnable model id
            fallback_agent=DEFAULT_MODEL,
            reasoning=f"ok: {strategy} | {reason}",
            confidence=float(confidence),
            session_id=getattr(request, "session_id", "") or "",
            task_id=getattr(request, "task_id", "") or "",
            routing_strategy=strategy,
            alternative_agents=[],            # could add other pipelines later
            parameters=params,
        )

    def _fallback(self, request, reason: str) -> langgraph_pb2.RoutingResponse:
        return self._resp(
            request=request,
            model=DEFAULT_MODEL,
            pipeline_id="default_v1",
            confidence=0.0,
            strategy="fallback",
            reason=reason,
        )

    def _apply_rules(self, task_type: str, content: str) -> Optional[Tuple[str, str, float, str]]:
        for rule in self._rules:
            ok = False
            if rule.task_type_in and task_type in rule.task_type_in:
                ok = True
            if rule.contains_any and any(k in content for k in rule.contains_any):
                ok = True
            if ok:
                return rule.model, rule.pipeline_id, rule.confidence, rule.strategy
        return None

    def GetRoutingDecision(self, request, context) -> langgraph_pb2.RoutingResponse:
        try:
            task_type = (getattr(request, "task_type", "") or "").lower()
            content = (getattr(request, "content", "") or "").lower()

            hit = self._apply_rules(task_type, content)
            if hit:
                model, pipeline_id, conf, strat = hit
                return self._resp(
                    request=request,
                    model=model,
                    pipeline_id=pipeline_id,
                    confidence=conf,
                    strategy=strat,
                    reason="rule_hit",
                )

            # Built-in fallback heuristics (no hard dependency on rules file)
            if task_type in ("translate", "translation") or ("翻译" in content) or ("translate" in content):
                return self._resp(request, DEFAULT_MODEL, "translate_v1", 0.70, "builtin.translate", "heuristic")
            if task_type in ("summarize", "summary") or ("总结" in content) or ("tl;dr" in content) or ("概括" in content):
                return self._resp(request, DEFAULT_MODEL, "summarize_v1", 0.65, "builtin.summarize", "heuristic")
            if task_type in ("code", "programming") or any(k in content for k in ["代码", "bug", "报错", "traceback", "exception", "stack"]):
                return self._resp(request, DEFAULT_MODEL, "code_v1", 0.65, "builtin.code", "heuristic")

            return self._resp(request, DEFAULT_MODEL, "default_v1", 0.60, "builtin.default", "heuristic")

        except Exception:
            logger.exception("❌ 路由决策异常")
            return self._fallback(request, "exception (see server traceback)")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    add_servicer_to_server(RoutingServicer(), server)

    listen_addr = f"0.0.0.0:{PORT}"
    server.add_insecure_port(listen_addr)
    server.start()

    logger.info("✅ LangGraph Routing 服务初始化完成")
    logger.info("🚀 LangGraph gRPC 服务启动，端口 %s", PORT)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在停止 LangGraph gRPC 服务...")
        server.stop(grace=3)


if __name__ == "__main__":
    serve()
