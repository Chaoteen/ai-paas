import os
import sys
from pathlib import Path
import types

import grpc
import pytest


REPO = Path("/home/boris/work/ai-paas")
PKG = "aios_sdk"
RPC_PATH = "/ai.os.langgraph.LangGraphRouter/GetRoutingDecision"


def _inject_empty_pkg(pkg: str, pkg_dir: Path) -> None:
    # Avoid executing aios_sdk/__init__.py if it has side effects
    if pkg in sys.modules:
        return
    m = types.ModuleType(pkg)
    m.__file__ = str(pkg_dir / "__init__.py")
    m.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    m.__package__ = pkg
    sys.modules[pkg] = m


@pytest.mark.integration
def test_grpc_langgraph_get_routing_decision_smoke():
    target = os.getenv("AI_PAAS_GRPC_TARGET", "127.0.0.1:50051")

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    _inject_empty_pkg(PKG, (REPO / "aios_sdk").resolve())

    langgraph_pb2 = __import__(f"{PKG}.langgraph_pb2", fromlist=["RoutingRequest"])
    RoutingRequest = getattr(langgraph_pb2, "RoutingRequest")

    req = RoutingRequest()  # empty request is OK for smoke

    md = (
        ("authorization", "Bearer dummy"),
        ("x-tenant-id", os.getenv("AI_PAAS_TENANT", "tenant_a")),
    )

    channel = grpc.insecure_channel(target)
    call = channel.unary_unary(
        RPC_PATH,
        request_serializer=req.SerializeToString,
        # IMPORTANT: keep raw bytes to avoid proto mismatch issues
        response_deserializer=lambda b: b,
    )

    try:
        _ = call(req, timeout=2.0, metadata=md)
        # If it returns OK, that's also fine for smoke
        assert True
    except grpc.RpcError as e:
        # The only thing we MUST NOT see here is UNIMPLEMENTED
        assert e.code() != grpc.StatusCode.UNIMPLEMENTED, f"Method not found: {RPC_PATH}"
