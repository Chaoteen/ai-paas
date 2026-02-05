from __future__ import annotations
from pathlib import Path
import re
import sys

FILE = Path("langgraph/langgraph_grpc_server.py")

def main():
    if not FILE.exists():
        print("[fix] ERROR: missing", FILE)
        sys.exit(1)

    lines = FILE.read_text(encoding="utf-8").splitlines(True)

    bad_patterns = [
        re.compile(r'^\s*context\.set_code\(\s*grpc\.StatusCode\.INTERNAL\s*\)\s*$'),
        re.compile(r'^\s*context\.set_details\('),
        # 有些实现会写成 await context.abort(...) 或 context.abort(...)
        re.compile(r'^\s*(await\s+)?context\.abort\('),
    ]

    removed = 0
    kept = []
    for ln in lines:
        if any(p.search(ln) for p in bad_patterns):
            removed += 1
            continue
        kept.append(ln)

    FILE.write_text("".join(kept), encoding="utf-8")
    print(f"[fix] OK: removed {removed} problematic context.* INTERNAL lines from {FILE}")

if __name__ == "__main__":
    main()
