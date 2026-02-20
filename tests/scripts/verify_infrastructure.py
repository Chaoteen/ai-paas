#!/usr/bin/env python3
"""
AI-PaaS 平台 - 基础设施健康检查脚本 v4
修复：
1. OPA 测试传入正确的 input 数据
2. 移除 Control Plane 端口检查（它是库，不是独立服务）
"""

import socket
import urllib.request
import json
import sys
import os

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def check_port(host, port, service_name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"{GREEN}✓{RESET} {service_name}: 端口 {port} 监听正常")
            return True
        else:
            print(f"{RED}✗{RESET} {service_name}: 端口 {port} 未监听")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET} {service_name}: {str(e)}")
        return False

def check_http_endpoint(url, service_name, expected_status=200, headers=None, method='GET', data=None):
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header('Accept', 'application/json')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        if data:
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=5, data=json.dumps(data).encode())
        else:
            response = urllib.request.urlopen(req, timeout=5)
        if response.status == expected_status:
            print(f"{GREEN}✓{RESET} {service_name}: {url} 响应正常 ({response.status})")
            return True, response
        else:
            print(f"{YELLOW}⚠{RESET} {service_name}: {url} 状态码异常 ({response.status})")
            return False, response
    except Exception as e:
        print(f"{RED}✗{RESET} {service_name}: {url} 无法访问 - {str(e)}")
        return False, None

def check_opa_policy():
    """检查 OPA 策略是否生效 - 传入正确的 input 数据"""
    url = "http://127.0.0.1:8181/v1/data/ui/allow"
    
    # 测试 1: 管理员用户访问 admin 菜单（应该 allow）
    admin_input = {
        "input": {
            "user": {"is_admin": True, "user_id": "admin"},
            "resource": {"kind": "menu", "id": "admin"}
        }
    }
    
    try:
        req = urllib.request.Request(url, method='POST')
        req.add_header('Content-Type', 'application/json')
        response = urllib.request.urlopen(req, timeout=5, data=json.dumps(admin_input).encode())
        data = json.loads(response.read().decode())
        if data.get("result") == True:
            print(f"{GREEN}✓{RESET} OPA 策略：管理员访问 admin 菜单 → allow")
            return True
        else:
            print(f"{YELLOW}⚠{RESET} OPA 策略：管理员访问 admin 菜单 → deny (预期 allow)")
            print(f"   响应：{data}")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET} OPA 策略：无法连接 - {str(e)}")
        return False

def check_redis():
    try:
        import redis
        r = redis.Redis(host='127.0.0.1', port=6379, socket_timeout=2)
        r.ping()
        print(f"{GREEN}✓{RESET} Redis: 连接正常 (PONG)")
        return True
    except ImportError:
        return check_port("127.0.0.1", 6379, "Redis")
    except Exception as e:
        print(f"{RED}✗{RESET} Redis: {str(e)}")
        return False

def main():
    print("=" * 60)
    print(f"{BLUE}AI-PaaS 平台 - 基础设施健康检查 v4{RESET}")
    print("=" * 60)
    print()
    print("启动依赖顺序：Redis → OPA → Agent Broker → Gateway → Frontend")
    print()
    
    results = []
    
    # === 基础设施层 ===
    print(f"{BLUE}【一、基础设施层】{RESET}")
    print("-" * 40)
    
    print("\n[1/7] 检查 Redis...")
    results.append(check_redis())
    
    print("\n[2/7] 检查 OPA 服务...")
    results.append(check_port("127.0.0.1", 8181, "OPA"))
    
    print("\n[3/7] 检查 OPA 策略...")
    results.append(check_opa_policy())
    
    # === Agent Core 层 ===
    print(f"\n{BLUE}【二、Agent Core 层】{RESET}")
    print("-" * 40)
    
    print("\n[4/7] 检查 Router Bridge...")
    import subprocess
    try:
        result = subprocess.run(['pgrep', '-f', 'router_bridge'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().split('\n')[0]
            print(f"{GREEN}✓{RESET} Router Bridge: 进程运行中 (PID: {pid})")
            results.append(True)
        else:
            print(f"{RED}✗{RESET} Router Bridge: 进程未运行")
            results.append(False)
    except Exception as e:
        print(f"{YELLOW}⚠{RESET} Router Bridge: 无法检查进程 - {str(e)}")
        results.append(False)
    
    print("\n[5/7] 检查 Model Worker...")
    try:
        result = subprocess.run(['pgrep', '-f', 'model_worker'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pid = result.stdout.strip().split('\n')[0]
            print(f"{GREEN}✓{RESET} Model Worker: 进程运行中 (PID: {pid})")
            results.append(True)
        else:
            print(f"{RED}✗{RESET} Model Worker: 进程未运行")
            results.append(False)
    except Exception as e:
        print(f"{YELLOW}⚠{RESET} Model Worker: 无法检查进程 - {str(e)}")
        results.append(False)
    
    # === Gateway 层 ===
    print(f"\n{BLUE}【三、Gateway 层】{RESET}")
    print("-" * 40)
    
    print("\n[6/7] 检查 Gateway...")
    results.append(check_port("127.0.0.1", 8000, "Gateway"))
    
    # === Frontend 层 ===
    print(f"\n{BLUE}【四、Frontend 层】{RESET}")
    print("-" * 40)
    
    print("\n[7/7] 检查 Frontend...")
    results.append(check_port("127.0.0.1", 5173, "Frontend Vite"))
    
    # === 汇总 ===
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"检查结果：{passed}/{total} 通过")
    
    if passed == total:
        print(f"{GREEN}✓ 所有基础服务运行正常，可进行下一步测试{RESET}")
        return 0
    else:
        print(f"{RED}✗ 部分服务异常，请先启动或修复相关服务{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())