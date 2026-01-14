import os
import subprocess

PROTO_DIR = "proto"
OUTPUT_DIR = "aios_sdk"

def generate_proto():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    protos = [f for f in os.listdir(PROTO_DIR) if f.endswith(".proto")]

    for proto_file in protos:
        proto_path = os.path.join(PROTO_DIR, proto_file)
        print(f"🧩 Generating gRPC for {proto_file} ...")

        subprocess.run([
            "python", "-m", "grpc_tools.protoc",
            f"--proto_path={PROTO_DIR}",
            f"--python_out={OUTPUT_DIR}",
            f"--grpc_python_out={OUTPUT_DIR}",
            proto_path
        ], check=True)

    # 修复 import 路径问题
    for root, _, files in os.walk(OUTPUT_DIR):
        for f in files:
            if f.endswith("_pb2_grpc.py"):
                path = os.path.join(root, f)
                with open(path, "r+", encoding="utf-8") as file:
                    content = file.read().replace("import ", "from . import ")
                    file.seek(0)
                    file.write(content)
                    file.truncate()

    print("✅ gRPC SDK generation complete!")


if __name__ == "__main__":
    generate_proto()