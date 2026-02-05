import socket
import sys
import grpc

from grpc_health.v1 import health_pb2, health_pb2_grpc

HOST = "127.0.0.1"
PORT = 50051
TARGET = f"{HOST}:{PORT}"

def tcp_check(host: str, port: int, timeout: float = 1.0) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
    finally:
        s.close()

def main() -> int:
    print(f"== TCP check {TARGET} ==")
    try:
        tcp_check(HOST, PORT, timeout=1.0)
        print("TCP OK")
    except Exception as e:
        print("TCP FAILED:", repr(e))
        return 2

    print(f"\n== gRPC Health Check: {TARGET} ==")
    channel = grpc.insecure_channel(TARGET)
    stub = health_pb2_grpc.HealthStub(channel)

    # 约定：service="" 表示 overall server health
    req = health_pb2.HealthCheckRequest(service="")
    try:
        resp = stub.Check(req, timeout=2.0)
        print("Health status:", health_pb2.HealthCheckResponse.ServingStatus.Name(resp.status))
        return 0
    except grpc.RpcError as e:
        print("Health RPC failed.")
        print("  code:", e.code())
        print("  details:", e.details())
        # 常见：UNIMPLEMENTED 表示没启用 health 服务
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
