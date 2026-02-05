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

def call(md):
    langgraph_pb2 = importlib.import_module(f"{PKG}.langgraph_pb2")
    RoutingRequest = getattr(langgraph_pb2, "RoutingRequest")
    req = RoutingRequest()

    channel = grpc.insecure_channel(TARGET)
    unary = channel.unary_unary(
        RPC_PATH,
        request_serializer=req.SerializeToString,
        response_deserializer=lambda b: b,
    )
    try:
        _ = unary(req, timeout=2.0, metadata=md)
        return ("OK", None)
    except grpc.RpcError as e:
        return (e.code(), e.details())

def main() -> int:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    inject_empty_pkg(PKG, (REPO / "aios_sdk").resolve())

    print("rpc_path:", RPC_PATH)
    print("target  :", TARGET)
    print("")

    md_with_auth = (
        ("authorization", "Bearer dummy"),
        ("x-tenant-id", "tenant_a"),
    )
    md_no_auth = (
        ("x-tenant-id", "tenant_a"),
    )
    md_no_tenant = (
        ("authorization", "Bearer dummy"),
    )

    r1 = call(md_with_auth)
    print("[with auth + tenant] ->", r1)

    r2 = call(md_no_auth)
    print("[no auth, tenant only] ->", r2)

    r3 = call(md_no_tenant)
    print("[auth only, no tenant] ->", r3)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
