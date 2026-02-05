from __future__ import annotations
from pathlib import Path
import re
import sys

FILE = Path("langgraph/langgraph_grpc_server.py")

def die(msg: str):
    print("[patch] ERROR:", msg)
    sys.exit(1)

def main():
    if not FILE.exists():
        die(f"missing file: {FILE}")

    src = FILE.read_text(encoding="utf-8").splitlines(True)

    # Quick sanity: file should be parseable-ish; but we already know it's broken.
    text = "".join(src)

    # Find the problematic INTERNAL block line to locate the except region
    # We'll replace the whole except block that contains 'context.set_code(grpc.StatusCode.INTERNAL)'
    needle = "context.set_code(grpc.StatusCode.INTERNAL)"
    idx = None
    for i, line in enumerate(src):
        if needle in line:
            idx = i
            break
    if idx is None:
        die("cannot find 'context.set_code(grpc.StatusCode.INTERNAL)' - file structure differs")

    # Walk upward to find the start of the 'except' block
    # We assume Python indentation with spaces.
    ex_start = None
    for i in range(idx, -1, -1):
        if re.match(r'^\s*except\b', src[i]):
            ex_start = i
            break
    if ex_start is None:
        die("cannot find surrounding 'except' block start")

    # Determine indentation of that except
    ex_indent = re.match(r'^(\s*)', src[ex_start]).group(1)

    # Walk downward to find end of except block (next line with indentation <= ex_indent and not blank/comment)
    ex_end = None
    for i in range(ex_start + 1, len(src)):
        line = src[i]
        if line.strip() == "":
            continue
        # Next 'except/elif/else/finally/def/class/async def/return' at same or less indent ends the block
        indent = re.match(r'^(\s*)', line).group(1)
        if len(indent) <= len(ex_indent) and not line.lstrip().startswith(("#",)):
            ex_end = i
            break
    if ex_end is None:
        ex_end = len(src)

    # Build replacement except block with correct indentation
    # Note: we return a RoutingResponse fallback and DO NOT call context.set_code.
    repl = []
    repl.append(f"{ex_indent}except Exception:\n")
    repl.append(f"{ex_indent}    logger.exception(\"❌ 标准化路由决策失败\")\n")
    repl.append(f"{ex_indent}    # Fallback: never raise gRPC INTERNAL; return a safe default decision\n")
    repl.append(f"{ex_indent}    return langgraph_pb2.RoutingResponse(\n")
    repl.append(f"{ex_indent}        target_agent=\"deepseek-r1:latest\",\n")
    repl.append(f"{ex_indent}        fallback_agent=\"deepseek-r1:latest\",\n")
    repl.append(f"{ex_indent}        reasoning=\"fallback: langgraph error (see server traceback)\",\n")
    repl.append(f"{ex_indent}        confidence=0.0,\n")
    repl.append(f"{ex_indent}        session_id=getattr(request, \"session_id\", \"\") or \"\",\n")
    repl.append(f"{ex_indent}        task_id=getattr(request, \"task_id\", \"\") or \"\",\n")
    repl.append(f"{ex_indent}        routing_strategy=\"fallback\",\n")
    repl.append(f"{ex_indent}        alternative_agents=[],\n")
    repl.append(f"{ex_indent}    )\n")

    new_src = src[:ex_start] + repl + src[ex_end:]
    FILE.write_text("".join(new_src), encoding="utf-8")
    print(f"[patch] OK: replaced except-block with fallback in {FILE}")
    print(f"[patch] touched lines ~{ex_start+1}-{ex_end}")

if __name__ == "__main__":
    main()
