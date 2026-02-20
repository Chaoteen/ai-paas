#!/usr/bin/env python3
"""
AI-PaaS 平台 - API 功能测试脚本
"""

import urllib.request
import json
import sys

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def test_endpoint(url, method='GET', data=None, expected_status=200, description=""):
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header('Accept', 'application/json')
        if data:
            req.add_header('Content-Type', 'application/json')
            response = urllib.request.urlopen(req, timeout=10, data=json.dumps(data).encode())
        else:
            response = urllib.request.urlopen(req, timeout=10)
        
        body = response.read().decode()
        
        if response.status == expected_status:
            print(f"{GREEN}✓{RESET} {description}")
            print(f"   URL: {url} → {response.status}")
            return True, json.loads(body) if body else {}
        else:
            print(f"{YELLOW}⚠{RESET} {description}")
            print(f"   URL: {url} → 状态码 {response.status}")
            return False, json.loads(body) if body else {}
    except Exception as e:
        print(f"{RED}✗{RESET} {description}")
        print(f"   URL: {url} → 错误：{str(e)}")
        return False, None

def main():
    print("=" * 60)
    print("AI-PaaS 平台 - API 功能测试")
    print("=" * 60)
    print()
    
    results = []
    gateway_base = "http://127.0.0.1:8000"
    
    print("[1/5] Gateway 健康检查...")
    success, _ = test_endpoint(f"{gateway_base}/api/health", description="Gateway /api/health")
    results.append(success)
    
    print("\n[2/5] UI Bootstrap（菜单加载）...")
    success, data = test_endpoint(f"{gateway_base}/api/ui/bootstrap", description="Gateway /api/ui/bootstrap")
    if success and data:
        print(f"   返回数据：{json.dumps(data, indent=2)[:300]}...")
    results.append(success)
    
    print("\n[3/5] OPA 策略判定（管理员）...")
    opa_input = {"input": {"user": {"is_admin": True}, "resource": {"kind": "menu", "id": "admin"}}}
    success, data = test_endpoint("http://127.0.0.1:8181/v1/data/ui/allow", method='POST', data=opa_input, description="OPA 管理员判定")
    if success and data:
        print(f"   结果：allow = {data.get('result')}")
    results.append(success)
    
    print("\n[4/5] OPA 策略判定（普通用户）...")
    opa_input2 = {"input": {"user": {"is_admin": False}, "resource": {"kind": "menu", "id": "chat"}}}
    success, data = test_endpoint("http://127.0.0.1:8181/v1/data/ui/allow", method='POST', data=opa_input2, description="OPA 普通用户判定")
    if success and data:
        print(f"   结果：allow = {data.get('result')}")
    results.append(success)
    
    print("\n[5/5] PromptFlow 服务...")
    success, _ = test_endpoint("http://127.0.0.1:8080/swagger.json", description="PromptFlow Swagger")
    results.append(success)
    
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    
    if passed == total:
        print(f"{GREEN}✓ 所有 API 功能测试通过{RESET}")
        return 0
    else:
        print(f"{YELLOW}⚠ 部分测试未通过{RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
