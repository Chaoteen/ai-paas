import sys
from pathlib import Path
import importlib.util

from google.protobuf.descriptor import FileDescriptor

REPO = Path("/home/boris/work/ai-paas")

def load_module_from_path(py_file: Path):
    # 以文件路径加载模块，避免 import package 触发副作用
    mod_name = "pb2_" + py_file.stem
    spec = importlib.util.spec_from_file_location(mod_name, str(py_file))
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    except Exception as e:
        return ("ERR", py_file, e)
    return ("OK", py_file, mod)

def main() -> int:
    pb2_files = sorted(REPO.rglob("*_pb2.py"))
    if not pb2_files:
        print("❌ No *_pb2.py found under repo. Check your generated protobuf outputs.")
        return 2

    services = {}
    errors = []

    for f in pb2_files:
        r = load_module_from_path(f)
        if r is None:
            continue
        tag = r[0]
        if tag == "ERR":
            _, path, err = r
            # 只记录前几个错误，避免刷屏
            errors.append((path, err))
            continue

        _, path, mod = r
        desc = getattr(mod, "DESCRIPTOR", None)
        if isinstance(desc, FileDescriptor):
            for svc in desc.services_by_name.values():
                services[svc.full_name] = svc

    if errors:
        print(f"⚠️ Loaded pb2 with {len(errors)} error(s). Showing up to 8:")
        for p, e in errors[:8]:
            print(f"  - {p}: {type(e).__name__}: {e}")
        print()

    if not services:
        print("❌ No gRPC services found in loaded DESCRIPTORs.")
        print("Hint: you may only have message defs, or service defs are in *_pb2_grpc.py.")
        return 3

    print(f"✅ Found {len(services)} service(s):\n")
    for name in sorted(services.keys()):
        svc = services[name]
        print(f"Service: {svc.full_name}")
        for m in svc.methods:
            print(f"  - {m.name}({m.input_type.full_name}) returns ({m.output_type.full_name})")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
