#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
import importlib
import types
import grpc

TARGET = "127.0.0.1:50051"
METHODS_JSON = "/tmp/grpc_methods.json"

REPO = Path("/home/boris/work/ai-paas")
PKG = "aios_sdk"
SERVICE_PREFIX = "/ai.os.langgraph.LangGraphRouter/"

def inject_empty_pkg(pkg: str, pkg_dir: Path):
    if pkg in sys.modules:
        return
    m = types.ModuleType(pkg)
    m.__file__ = str(pkg_dir / "__init__.py")
    m.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    m.__package__ = pkg
    sys.modules[pkg] = m

def resolve_msg_class(req_type: str):
    if "__pb2." in req_type:
        mod_short, cls = req_type.split("__pb2.", 1)
        return f"{mod_short}_pb2", cls
    parts = req_type.split(".")
    return ".".join(parts[:-1]), parts[-1]

def main() -> int:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    sdk_dir = (REPO / "aios_sdk").resolve()
    inject_empty_pkg(PKG, sdk_dir)

    p = Path(METHODS_JSON)
    if not p.exists():
        print(f"❌ {METHODS_JSON} not found. Run extractor first.")
        return 2

    data = json.loads(p.read_text(encoding="utf-8"))
    methods = [
        m for m in data.get("methods", [])
        if m.get("kind") == "unary_unary" and m.get("rpc_path", "").startswith(SERVICE_PREFIX)
    ]

    if not methods:
        print("❌ No LangGraphRouter unary_unary methods found in json.")
        return 3

    langgraph_pb2 = importlib.import_module(f"{PKG}.langgraph_pb2")
    Envelope = importlib.import_module(f"{PKG}.envelope_pb2").s if hasattr(importlib.import_module(f"{PKG}.envelope_pb2"), "S") else None  # unused fallback

    md = (
        ("authorization", "Bearer dummy"),
        ("x-tenant-id", "tenant_a"),
    )

    channel = grpc.insecure_channel(TARGET)

    print(f"== Probing LangGraphRouter unary_unary methods ({len(methods)}) against {TARGET} ==")
    hits = []

    for m in methods:
        rpc_path = m["rpc_path"]
        req_type = m["request_type"]

        pb2_mod, cls = resolve_msg_class(req_type)
        mod_name = f"{PKG}.{pb2_mod}" if pb2_mod.endswith("_pb2") else pb2_mod

        try:
            mod = importlib.import_module(mod_name)
            Req = getattr(mod, cls)
            req = Req()
            ser = req.SerializeToString
        except Exception as e:
            # If request type cannot be resolved, skip (we want clean signal)
            print(f"[SKIP] {rpc_path} (cannot build request: {e})")
            continue

        call = channel.unary_unary(rpc_path, request_serializer=ser, response_deserializer=lambda b: b)
        try:
            _ = call(req, timeout=1.5, metadata=md)
            print(f"[HIT]  {rpc_path} -> OK")
            hits.append((rpc_path, "OK", ""))
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.UNIMPLEMENTED:
                print(f"[HIT]  {rpc_path} -> {e.code()} ({e.details()})")
                hits.append((rpc_path, str(e.code()), e.details() or ""))
            else:
                print(f"[MISS] {rpc_path} -> UNIMPLEMENTED")

    print("\n== HIT summary ==")
    for rpc_path, code, details in hits:
        print(f"- {rpc_path} -> {code} {details}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
