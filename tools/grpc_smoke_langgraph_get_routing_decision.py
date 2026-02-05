#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import importlib
import types
import grpc

TARGET = "127.0.0.1:50051"
RPC_PATH = "/ai.os.langgraph.LangGraphRouter/GetRoutingDecision"

REPO = Path("/home/boris/work/ai-paas")
PKG = "aios_sdk"

def inject_empty_pkg(pkg: str, pkg_dir: Path):
    if pkg in sys.modules:
        return
    m = types.ModuleType(pkg)
    m.__file__ = str(pkg_dir / "__init__.py")
    m.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    m.__package__ = pkg
    sys.modules[pkg] = m

def main() -> int:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    sdk_dir = (REPO / "aios_sdk").resolve()
    inject_empty_pkg(PKG, sdk_dir)

    # request type from your extracted list: langgraph__pb2.RoutingRequest
    langgraph_pb2 = importlib.import_module(f"{PKG}.langgraph_pb2")
    RoutingRequest = getattr(langgraph_pb2, "RoutingRequest")
    req = RoutingRequest()  # empty request; server may return INVALID_ARGUMENT/INTERNAL, both prove method exists

    md = (
        ("authorization", "Bearer dummy"),
        ("x-tenant-id", "tenant_a"),
    )

    channel = grpc.insecure_channel(TARGET)
    call = channel.unary_unary(
        RPC_PATH,
        request_serializer=req.SerializeToString,
        response_deserializer=lambda b: b,  # IMPORTANT: avoid proto mismatch by keeping raw bytes
    )

    print("rpc_path:", RPC_PATH)
    print("target  :", TARGET)
    print("== calling (expect NOT UNIMPLEMENTED) ==")

    try:
        resp_bytes = call(req, timeout=2.0, metadata=md)
        print("✅ OK (unexpected for empty request). resp_bytes_len =", len(resp_bytes))
        return 0
    except grpc.RpcError as e:
        print("✅ gRPC error returned (expected).")
        print("code   :", e.code())
        print("details:", e.details())
        if e.code() == grpc.StatusCode.UNIMPLEMENTED:
            print("❌ Unexpected: method not found. This would contradict the probe result.")
            return 3
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
