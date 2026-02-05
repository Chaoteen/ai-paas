#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LangGraph gRPC smoke test (production contract)

Fix: grpc Stub methods are often attached at INSTANCE level (in __init__),
so we must inspect stub instances rather than classes.

Exit code:
- 0 success
- 2 contract failed
- 3 gRPC call failed
- 4 could not find suitable stub/method
"""

from __future__ import annotations

import os
import sys
import uuid
import argparse
import grpc
from typing import List, Tuple, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aios_sdk import langgraph_pb2, langgraph_pb2_grpc  # type: ignore


def _list_stub_classes():
    stubs = []
    for name in dir(langgraph_pb2_grpc):
        if not name.endswith("Stub"):
            continue
        cls = getattr(langgraph_pb2_grpc, name)
        if isinstance(cls, type):
            stubs.append((name, cls))
    # prefer names that look like routing/router
    stubs.sort(key=lambda x: (("route" not in x[0].lower() and "routing" not in x[0].lower() and "router" not in x[0].lower()), x[0]))
    return stubs


def _pick_request_message():
    """
    Find a request message type that has fields: task_type, content.
    """
    msg_types = []
    for name in dir(langgraph_pb2):
        obj = getattr(langgraph_pb2, name)
        if not isinstance(obj, type):
            continue
        if not hasattr(obj, "DESCRIPTOR"):
            continue
        try:
            fields = {f.name for f in obj.DESCRIPTOR.fields}
        except Exception:
            continue
        if "task_type" in fields and "content" in fields:
            msg_types.append(obj)

    if not msg_types:
        raise RuntimeError("No request message with fields {task_type, content} found in langgraph_pb2")

    msg_types.sort(key=lambda t: (("route" not in t.__name__.lower() and "routing" not in t.__name__.lower()), t.__name__))
    return msg_types[0]


def _find_rpc_method(stub_obj, preferred: str) -> Tuple[Optional[str], List[str]]:
    """
    Return (method_name, available_rpc_methods)
    - Detect unary_unary callables attached on the stub instance
    """
    rpc_names = []
    for attr in dir(stub_obj):
        if attr.startswith("_"):
            continue
        val = getattr(stub_obj, attr, None)
        # gRPC callables are callable
        if callable(val):
            rpc_names.append(attr)

    # exact match first
    if preferred in rpc_names:
        return preferred, rpc_names

    # heuristic match
    candidates = [n for n in rpc_names if "routing" in n.lower() or "route" in n.lower() or "decision" in n.lower()]
    if candidates:
        # stable preference order
        candidates.sort(key=lambda n: (("routing" not in n.lower() and "route" not in n.lower()), n))
        return candidates[0], rpc_names

    return None, rpc_names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default=os.getenv("LANGGRAPH_ADDR", "127.0.0.1:50051"))
    ap.add_argument("--method", default=os.getenv("LANGGRAPH_METHOD", "GetRoutingDecision"))
    ap.add_argument("--task-type", default="translate")
    ap.add_argument("--content", default="把 hello 翻译成中文")
    ap.add_argument("--session-id", default=f"s_{uuid.uuid4().hex[:8]}")
    ap.add_argument("--task-id", default=f"t_{uuid.uuid4().hex[:8]}")
    args = ap.parse_args()

    Req = _pick_request_message()
    req_fields = {f.name for f in Req.DESCRIPTOR.fields}

    req_kwargs = {"task_type": args.task_type, "content": args.content}
    if "session_id" in req_fields:
        req_kwargs["session_id"] = args.session_id
    if "task_id" in req_fields:
        req_kwargs["task_id"] = args.task_id
    request = Req(**req_kwargs)

    stub_classes = _list_stub_classes()
    if not stub_classes:
        print("[FAIL] No *Stub classes found in aios_sdk.langgraph_pb2_grpc")
        raise SystemExit(4)

    last_rpc_list = None
    try:
        with grpc.insecure_channel(args.addr) as channel:
            chosen = None
            chosen_rpc = None

            # Try stubs in order; pick first that exposes a routing-ish RPC
            for stub_name, StubCls in stub_classes:
                stub = StubCls(channel)
                rpc_name, rpc_list = _find_rpc_method(stub, args.method)
                last_rpc_list = (stub_name, rpc_list)
                if rpc_name:
                    chosen = (stub_name, stub)
                    chosen_rpc = rpc_name
                    break

            if not chosen or not chosen_rpc:
                print("[FAIL] Could not find a suitable RPC method on any Stub instance.")
                if last_rpc_list:
                    sn, rpcs = last_rpc_list
                    print(f"  Last inspected stub: {sn}")
                    print(f"  Available callables: {rpcs}")
                print("  Tip: run with --method <one of the callables above>")
                raise SystemExit(4)

            stub_name, stub = chosen
            rpc = getattr(stub, chosen_rpc)

            resp = rpc(request, timeout=3.0)

    except SystemExit:
        raise
    except Exception as e:
        print(f"[FAIL] gRPC call failed: {e}")
        raise SystemExit(3)

    # Contract assertions
    ok = True
    problems = []

    target_agent = getattr(resp, "target_agent", "")
    if not target_agent:
        ok = False
        problems.append("target_agent is empty")

    params = getattr(resp, "parameters", None)
    pipeline_id = None
    if params is None:
        ok = False
        problems.append("parameters map is missing")
    else:
        pipeline_id = params.get("pipeline_id")
        if not pipeline_id:
            ok = False
            problems.append('parameters["pipeline_id"] missing or empty')

    # Echo checks
    if hasattr(resp, "session_id") and "session_id" in req_kwargs:
        if resp.session_id != req_kwargs["session_id"]:
            ok = False
            problems.append(f"session_id not echoed: want={req_kwargs['session_id']} got={resp.session_id}")

    if hasattr(resp, "task_id") and "task_id" in req_kwargs:
        if resp.task_id != req_kwargs["task_id"]:
            ok = False
            problems.append(f"task_id not echoed: want={req_kwargs['task_id']} got={resp.task_id}")

    print("[OK] gRPC call succeeded")
    print(f"  stub   : {stub_name}")
    print(f"  method : {chosen_rpc}")
    print("[OK] Response:")
    print(f"  target_agent: {target_agent}")
    print(f"  pipeline_id : {pipeline_id}")
    print(f"  confidence  : {getattr(resp, 'confidence', None)}")
    print(f"  strategy    : {getattr(resp, 'routing_strategy', '')}")
    print(f"  reasoning   : {getattr(resp, 'reasoning', '')}")

    if not ok:
        print("[FAIL] Contract failed:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(2)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
