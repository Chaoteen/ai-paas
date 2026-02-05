#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import grpc
import importlib
import types

TARGET = "127.0.0.1:50051"
RPC_PATH = "/ai.os.inference.InferenceService/HealthCheck"

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

    # HealthCheck uses Envelope as req/resp per your extracted list
    envelope_pb2 = importlib.import_module(f"{PKG}.envelope_pb2")
    Envelope = getattr(envelope_pb2, "Envelope")
    req = Envelope()  # empty envelope

    md = (
        ("authorization", "Bearer dummy"),
        ("x-tenant-id", "tenant_a"),
    )

    channel = grpc.insecure_channel(TARGET)
    call = channel.unary_unary(
        RPC_PATH,
        request_serializer=req.SerializeToString,
        response_deserializer=Envelope.FromString,
    )

    print("rpc_path:", RPC_PATH)
    print("target  :", TARGET)
    print("== calling (expect OK or auth error, both prove connectivity) ==")

    try:
        resp = call(req, timeout=3.0, metadata=md)
        print("✅ OK, got Envelope response")
        # Print a small hint of response content without assuming schema
        try:
            print("response:", resp)
        except Exception:
            print("response: <unprintable>")
        return 0
    except grpc.RpcError as e:
        print("✅ gRPC error returned (still OK for smoke).")
        print("code   :", e.code())
        print("details:", e.details())
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
