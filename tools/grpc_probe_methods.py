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

# 只探测这些关键字（低风险、通常存在）
PREFERRED_KEYWORDS = ("Health", "Status", "Get", "List", "Info", "Version", "Ping", "Who")

def inject_empty_pkg(pkg: str, pkg_dir: Path):
    if pkg in sys.modules:
        return
    m = types.ModuleType(pkg)
    m.__file__ = str(pkg_dir / "__init__.py")
    m.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    m.__package__ = pkg
    sys.modules[pkg] = m

def resolve_msg_class(req_type: str):
    # req_type like "inference__pb2.InferenceRequest"
    if "__pb2." in req_type:
        mod_short, cls = req_type.split("__pb2.", 1)
        pb2_mod = f"{mod_short}_pb2"
        return pb2_mod, cls
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
    methods = [m for m in data.get("methods", []) if m.get("kind") == "unary_unary"]

    # 优先探测“看起来安全”的
    def score(m):
        path = m["rpc_path"]
        return sum(1 for k in PREFERRED_KEYWORDS if k in path)

    methods.sort(key=score, reverse=True)

    # 只探测前 N 个，避免过多请求（先 20 个足够定位）
    N = 20
    methods = methods[:N]

    envelope_mod = importlib.import_module(f"{PKG}.envelope_pb2")
    Envelope = getattr(envelope_mod, "Envelope")

    md = (
        ("authorization", "Bearer dummy"),
        ("x-tenant-id", "tenant_a"),
    )

    channel = grpc.insecure_channel(TARGET)

    print(f"== Probing unary_unary methods (top {N}) against {TARGET} ==")

    hits = 0
    for m in methods:
        rpc_path = m["rpc_path"]
        req_type = m["request_type"]

        # build empty request
        pb2_mod, cls = resolve_msg_class(req_type)
        mod_name = f"{PKG}.{pb2_mod}" if pb2_mod.endswith("_pb2") else pb2_mod
        try:
            mod = importlib.import_module(mod_name)
            Req = getattr(mod, cls)
            req = Req()
            ser = req.SerializeToString
            # response deserializer: try Envelope first, else raw bytes
            deser = Envelope.FromString
        except Exception:
            # 如果 request 类型解析失败，用 Envelope 兜底（很多内部服务用 Envelope）
            req = Envelope()
            ser = req.SerializeToString
            deser = Envelope.FromString

        call = channel.unary_unary(rpc_path, request_serializer=ser, response_deserializer=deser)
        try:
            _ = call(req, timeout=1.5, metadata=md)
            print(f"[HIT] {rpc_path} -> OK")
            hits += 1
        except grpc.RpcError as e:
            code = e.code()
            if code != grpc.StatusCode.UNIMPLEMENTED:
                print(f"[HIT] {rpc_path} -> {code}  ({e.details()})")
                hits += 1
            else:
                print(f"[MISS] {rpc_path} -> UNIMPLEMENTED")

    print(f"\n== Done. HITs={hits}/{N} (HIT means server recognized the method) ==")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
