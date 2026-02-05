#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

RE_METHOD = re.compile(
    r'self\.(?P<method>\w+)\s*=\s*channel\.(?P<kind>unary_unary|unary_stream|stream_unary|stream_stream)\(\s*'
    r'["\']/(?P<svc>[^/]+)/(?P<rpc>\w+)["\']\s*,'
    r'\s*request_serializer\s*=\s*(?P<req>[\w\.]+)\.SerializeToString\s*,'
    r'\s*response_deserializer\s*=\s*(?P<resp>[\w\.]+)\.FromString',
    re.MULTILINE
)

@dataclass
class RpcMethod:
    pb2_grpc_module: str
    stub_method_attr: str       # e.g. "Run"
    rpc_name: str               # e.g. "Run"
    service_full_name: str      # e.g. "aios.AgentService"
    rpc_path: str               # e.g. "/aios.AgentService/Run"
    kind: str                   # unary_unary / unary_stream / stream_unary / stream_stream
    request_type: str           # e.g. "agent__pb2.RunRequest"
    response_type: str          # e.g. "agent__pb2.RunReply"

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="/home/boris/work/ai-paas")
    p.add_argument("--sdk-dir", default="", help="Default: <repo-root>/aios_sdk")
    p.add_argument("--out", default="/tmp/grpc_methods.json")
    return p.parse_args()

def main() -> int:
    args = parse_args()
    repo = Path(args.repo_root).resolve()
    sdk = Path(args.sdk_dir).resolve() if args.sdk_dir else (repo / "aios_sdk")
    if not sdk.is_dir():
        print(f"❌ sdk dir not found: {sdk}")
        return 2

    pb2grpc_files = sorted(sdk.glob("*_pb2_grpc.py"))
    if not pb2grpc_files:
        print("❌ no *_pb2_grpc.py found")
        return 3

    methods: List[RpcMethod] = []
    for f in pb2grpc_files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in RE_METHOD.finditer(text):
            svc = m.group("svc")
            rpc = m.group("rpc")
            kind = m.group("kind")
            req = m.group("req")
            resp = m.group("resp")
            stub_attr = m.group("method")
            methods.append(RpcMethod(
                pb2_grpc_module=f.stem,
                stub_method_attr=stub_attr,
                rpc_name=rpc,
                service_full_name=svc,
                rpc_path=f"/{svc}/{rpc}",
                kind=kind,
                request_type=req,
                response_type=resp,
            ))

    payload = {
        "repo_root": str(repo),
        "sdk_dir": str(sdk),
        "count": len(methods),
        "methods": [asdict(x) for x in methods],
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ extracted {len(methods)} rpc method(s)")
    print(f"✅ wrote: {args.out}")

    # Print a compact preview
    preview = methods[:30]
    if preview:
        print("\nPreview (first 30):")
        for x in preview:
            print(f"- {x.rpc_path} [{x.kind}] req={x.request_type} resp={x.response_type}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
