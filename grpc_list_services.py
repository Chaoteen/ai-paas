import importlib
import pkgutil
import sys
from types import ModuleType
from google.protobuf.descriptor import FileDescriptor
from google.protobuf.descriptor import ServiceDescriptor

PB_PKG_CANDIDATES = [
    "aios_sdk",          # 你 repo 里现有的
    "aios_sdk.agent_pb", # 你目录里出现过这个
]

def iter_modules(pkg_name: str):
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception as e:
        return
    if not hasattr(pkg, "__path__"):
        return
    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        yield m.name

def extract_services_from_module(mod: ModuleType):
    services = []
    for v in mod.__dict__.values():
        if isinstance(v, FileDescriptor):
            for svc in v.services_by_name.values():
                services.append(svc)
    return services

def main() -> int:
    print("== Searching protobuf FileDescriptor in candidate packages ==")
    found_any = False
    all_services: list[ServiceDescriptor] = []

    for pkg in PB_PKG_CANDIDATES:
        for mod_name in [pkg, *list(iter_modules(pkg))]:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
            svcs = extract_services_from_module(mod)
            if svcs:
                found_any = True
                for s in svcs:
                    all_services.append(s)

    if not found_any:
        print("❌ No FileDescriptor/services found. Possible reasons:")
        print("1) pb2 modules not importable (PYTHONPATH issues)")
        print("2) pb2 generated with different package layout")
        print("Try: export PYTHONPATH=/home/boris/work/ai-paas")
        return 2

    # Deduplicate by full name
    uniq = {}
    for s in all_services:
        uniq[s.full_name] = s

    print(f"\n✅ Found {len(uniq)} service(s):\n")
    for full_name, svc in sorted(uniq.items(), key=lambda x: x[0]):
        print(f"Service: {full_name}")
        for m in svc.methods:
            # request/response full names
            print(f"  - {m.name}({m.input_type.full_name}) returns ({m.output_type.full_name})")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
