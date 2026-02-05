#!/usr/bin/env python3
# tools/grpc_list_services_safe.py
# Final version for ai-paas repo (WSL/Linux) - safe scan of pb2/pb2_grpc without side effects.

from __future__ import annotations

import argparse
import importlib
import json
import os
import pkgutil
import sys
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Data structures
# -----------------------------
@dataclass
class ServiceMethod:
    name: str
    input_type: str
    output_type: str
    client_streaming: bool
    server_streaming: bool


@dataclass
class ServiceInfo:
    package: str          # proto package, e.g. "aios"
    module: str           # python module stem, e.g. "agent_pb2"
    service_name: str     # proto service name, e.g. "AgentService"
    full_name: str        # fully qualified service name, e.g. "aios.AgentService"
    methods: List[ServiceMethod]


@dataclass
class GrpcSymbols:
    module: str
    stubs: List[str]
    servicers: List[str]
    add_to_server: List[str]


# -----------------------------
# Repo/path helpers
# -----------------------------
def _default_repo_root() -> Path:
    """
    Resolve repo root by script location:
      <repo>/tools/grpc_list_services_safe.py -> repo_root = parents[1]
    """
    return Path(__file__).resolve().parents[1]


def _resolve_sdk_dir(repo_root: Path, override: Optional[str]) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return (repo_root / "aios_sdk").resolve()


# -----------------------------
# Side-effect-free package injection
# -----------------------------
def _inject_empty_pkg(pkg_name: str, pkg_dir: Path) -> None:
    """
    Prevent executing aios_sdk/__init__.py (if it has side effects).
    We inject a minimal package module into sys.modules.

    After this, importlib.import_module("aios_sdk.xxx_pb2") will NOT execute __init__.py,
    but still resolve submodules via __path__.
    """
    if pkg_name in sys.modules:
        # If already imported, we keep it (could have side effects already).
        return

    m = types.ModuleType(pkg_name)
    m.__file__ = str(pkg_dir / "__init__.py")
    m.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    m.__package__ = pkg_name
    sys.modules[pkg_name] = m


# -----------------------------
# Module scanning (filesystem)
# -----------------------------
def _iter_modules_in_dir(sdk_dir: Path) -> Tuple[List[str], List[str]]:
    """
    Only list modules in sdk_dir (non-packages), return:
      pb2_mods:      ["agent_pb2", ...]
      pb2_grpc_mods: ["agent_pb2_grpc", ...]
    """
    pb2_mods: List[str] = []
    pb2_grpc_mods: List[str] = []

    for _, modname, ispkg in pkgutil.iter_modules([str(sdk_dir)]):
        if ispkg:
            continue
        if modname.endswith("_pb2_grpc"):
            pb2_grpc_mods.append(modname)
        elif modname.endswith("_pb2"):
            pb2_mods.append(modname)

    pb2_mods.sort()
    pb2_grpc_mods.sort()
    return pb2_mods, pb2_grpc_mods


# -----------------------------
# Extract services from pb2
# -----------------------------
def _load_pb2_services(pkg: str, pb2_modname: str) -> List[ServiceInfo]:
    """
    Import aios_sdk.xxx_pb2 and read DESCRIPTOR.services.
    """
    mod = importlib.import_module(f"{pkg}.{pb2_modname}")
    desc = getattr(mod, "DESCRIPTOR", None)
    if desc is None:
        return []

    proto_pkg = getattr(desc, "package", "") or ""
    out: List[ServiceInfo] = []

    # desc.services is a list of ServiceDescriptor
    for svc in getattr(desc, "services", []) or []:
        methods: List[ServiceMethod] = []
        for m in svc.methods:
            methods.append(
                ServiceMethod(
                    name=m.name,
                    input_type=m.input_type.full_name,
                    output_type=m.output_type.full_name,
                    client_streaming=bool(m.client_streaming),
                    server_streaming=bool(m.server_streaming),
                )
            )
        full_name = f"{proto_pkg}.{svc.name}" if proto_pkg else svc.name
        out.append(
            ServiceInfo(
                package=proto_pkg,
                module=pb2_modname,
                service_name=svc.name,
                full_name=full_name,
                methods=methods,
            )
        )
    return out


# -----------------------------
# Extract stub/servicer symbols from pb2_grpc
# -----------------------------
def _load_grpc_symbols(pkg: str, pb2_grpc_modname: str) -> GrpcSymbols:
    mod = importlib.import_module(f"{pkg}.{pb2_grpc_modname}")
    stubs: List[str] = []
    servicers: List[str] = []
    add_servicer_fns: List[str] = []

    for name in dir(mod):
        if name.endswith("Stub"):
            stubs.append(name)
        elif name.endswith("Servicer"):
            servicers.append(name)
        elif name.startswith("add_") and name.endswith("_to_server"):
            add_servicer_fns.append(name)

    return GrpcSymbols(
        module=pb2_grpc_modname,
        stubs=sorted(stubs),
        servicers=sorted(servicers),
        add_to_server=sorted(add_servicer_fns),
    )


# -----------------------------
# Safe-method candidates (for next stage: smoke call)
# -----------------------------
SAFE_METHOD_PREFIX = (
    "Get", "List", "Describe", "Status", "Version", "Ping", "Health", "WhoAmI", "Whoami", "Info"
)
SAFE_METHOD_EXACT = ("Check",)  # sometimes service has Check() meaning read-only


def _is_safe_candidate(method_name: str, client_stream: bool, server_stream: bool) -> bool:
    # prefer unary-unary calls for smoke tests (easiest, minimal side effects)
    if client_stream or server_stream:
        return False
    if method_name in SAFE_METHOD_EXACT:
        return True
    return method_name.startswith(SAFE_METHOD_PREFIX)


def _collect_safe_candidates(services: List[ServiceInfo]) -> List[Tuple[str, str]]:
    """
    Return list of (service_full_name, method_name) for safe unary candidates.
    """
    out: List[Tuple[str, str]] = []
    for s in services:
        for m in s.methods:
            if _is_safe_candidate(m.name, m.client_streaming, m.server_streaming):
                out.append((s.full_name, m.name))
    return out


# -----------------------------
# CLI / Main
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Safely list gRPC services/methods from pb2/pb2_grpc in ai-paas repo.")
    p.add_argument("--repo-root", default=os.getenv("AIOS_REPO_ROOT", ""), help="Repo root path. Default: auto by script location.")
    p.add_argument("--sdk-dir", default=os.getenv("AIOS_SDK_DIR", ""), help="Path to aios_sdk directory. Default: <repo_root>/aios_sdk")
    p.add_argument("--pkg", default=os.getenv("AIOS_SDK_PKG", "aios_sdk"), help="Python package name (default: aios_sdk)")
    p.add_argument("--json", action="store_true", help="Output JSON instead of pretty text.")
    p.add_argument("--out", default="", help="Write output to file (optional).")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Resolve paths
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else _default_repo_root()
    sdk_dir = _resolve_sdk_dir(repo_root, args.sdk_dir if args.sdk_dir else None)

    if not sdk_dir.is_dir():
        print(f"❌ aios_sdk dir not found: {sdk_dir}")
        print("Hint: pass --sdk-dir or set AIOS_SDK_DIR")
        return 2

    # Ensure import path (parent of aios_sdk)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Inject empty pkg to avoid executing aios_sdk/__init__.py side effects
    _inject_empty_pkg(args.pkg, sdk_dir)

    pb2_mods, pb2_grpc_mods = _iter_modules_in_dir(sdk_dir)

    services: List[ServiceInfo] = []
    pb2_errors: List[Tuple[str, str]] = []
    for m in pb2_mods:
        try:
            services.extend(_load_pb2_services(args.pkg, m))
        except Exception as e:
            pb2_errors.append((m, f"{type(e).__name__}: {e}"))

    grpc_syms: List[GrpcSymbols] = []
    pb2_grpc_errors: List[Tuple[str, str]] = []
    for m in pb2_grpc_mods:
        try:
            grpc_syms.append(_load_grpc_symbols(args.pkg, m))
        except Exception as e:
            pb2_grpc_errors.append((m, f"{type(e).__name__}: {e}"))

    safe_candidates = _collect_safe_candidates(services)

    payload = {
        "repo_root": str(repo_root),
        "sdk_dir": str(sdk_dir),
        "pkg": args.pkg,
        "pb2_modules": pb2_mods,
        "pb2_grpc_modules": pb2_grpc_mods,
        "services": [asdict(s) for s in services],
        "grpc_symbols": [asdict(s) for s in grpc_syms],
        "safe_unary_candidates": [{"service": s, "method": m} for s, m in safe_candidates],
        "import_errors": {
            "pb2": [{"module": m, "error": err} for m, err in pb2_errors],
            "pb2_grpc": [{"module": m, "error": err} for m, err in pb2_grpc_errors],
        },
    }

    if args.json:
        out_text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        lines: List[str] = []
        lines.append(f"✅ repo_root: {repo_root}")
        lines.append(f"✅ sdk_dir  : {sdk_dir}")
        lines.append(f"✅ pkg      : {args.pkg}")
        lines.append(f"✅ found *_pb2      : {len(pb2_mods)}")
        lines.append(f"✅ found *_pb2_grpc : {len(pb2_grpc_mods)}")
        lines.append("")

        if pb2_errors:
            lines.append("⚠️ Import errors on some *_pb2 modules:")
            for m, err in pb2_errors:
                lines.append(f"  - {m}: {err}")
            lines.append("")

        if not services:
            lines.append("❌ No services found in any *_pb2 DESCRIPTOR.")
        else:
            lines.append("🚀 Services discovered:")
            for s in services:
                lines.append(f"\n- Service: {s.full_name}   (from {s.module}.py)")
                for meth in s.methods:
                    streaming = []
                    if meth.client_streaming:
                        streaming.append("client_stream")
                    if meth.server_streaming:
                        streaming.append("server_stream")
                    streaming_str = (" [" + ",".join(streaming) + "]") if streaming else ""
                    lines.append(f"    · {meth.name}{streaming_str}")
                    lines.append(f"        in : {meth.input_type}")
                    lines.append(f"        out: {meth.output_type}")

        lines.append("\n\n🔍 gRPC wrapper symbols (*_pb2_grpc.py):")
        if pb2_grpc_errors:
            lines.append("⚠️ Import errors on some *_pb2_grpc modules:")
            for m, err in pb2_grpc_errors:
                lines.append(f"  - {m}: {err}")
            lines.append("")

        for sym in grpc_syms:
            if not (sym.stubs or sym.servicers or sym.add_to_server):
                continue
            lines.append(f"\n- {sym.module}.py")
            if sym.stubs:
                lines.append(f"    Stubs: {', '.join(sym.stubs)}")
            if sym.servicers:
                lines.append(f"    Servicers: {', '.join(sym.servicers)}")
            if sym.add_to_server:
                lines.append(f"    add_to_server: {', '.join(sym.add_to_server)}")

        lines.append("\n\n🧪 Safe unary candidates (suggested for smoke-call next step):")
        if safe_candidates:
            for s, m in safe_candidates:
                lines.append(f"  - {s}/{m}")
        else:
            lines.append("  (none found by name heuristic; you may define your own allowlist)")

        lines.append("\n✅ Done.")
        out_text = "\n".join(lines)

    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"✅ wrote output to: {args.out}")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
