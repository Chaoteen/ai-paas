"""
Conversation API 集成测试
验证：创建会话 -> 发送消息 (SSE) -> 查询历史 -> Prompt 预览
"""
import requests
import json
import sys
import os

# 配置
BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"Content-Type": "application/json"}

# 测试数据 (请确保这些 ID 在你的数据库中存在)
# 运行 python check_db_schema.py 查看现有的 project_id
TEST_PROJECT_ID = "9dc5f322-2392-49a1-8455-2241afc1c4bb" 

def test_create_conversation():
    print("\n1️⃣ 测试创建会话...")
    payload = {
        "project_id": TEST_PROJECT_ID,
        "title": "API 测试会话",
        "agent_id": None
    }
    
    resp = requests.post(f"{BASE_URL}/conversations/", json=payload, headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        conv_id = data['id']
        print(f"   ✅ 会话创建成功：{conv_id}")
        return conv_id
    else:
        print(f"   ❌ 失败：{resp.status_code} - {resp.text}")
        # 如果 Project 不存在，尝试找一个存在的
        if "Project not found" in resp.text:
            print("   ⚠️ 提示：请修改脚本中的 TEST_PROJECT_ID 为你数据库中真实的项目 ID")
        return None

def test_send_message_sse(conv_id):
    print(f"\n2️⃣ 测试发送消息 (SSE 流式) - 会话：{conv_id}...")
    payload = {"content": "你好，这是一个测试消息", "role": "user"}
    
    try:
        # SSE 需要特殊处理，使用 stream=True
        resp = requests.post(
            f"{BASE_URL}/conversations/{conv_id}/messages", 
            json=payload, 
            headers=HEADERS, 
            stream=True
        )
        
        if resp.status_code != 200:
            print(f"   ❌ 请求失败：{resp.status_code} - {resp.text}")
            return False
            
        print("   📡 接收流式数据中...")
        received_tokens = []
        has_start = False
        has_end = False
        
        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data:"):
                    data_str = decoded[5:].strip()
                    if data_str == "[DONE]": break
                    
                    try:
                        data = json.loads(data_str)
                        event = data.get("event")
                        
                        if event == "start":
                            has_start = True
                            print(f"   ▶️ 开始 (MsgID: {data['data'].get('message_id')})")
                        elif event == "token":
                            received_tokens.append(data['data'])
                            # 实时打印最后一个字符，模拟打字机
                            # print(data['data'], end='', flush=True) 
                        elif event == "end":
                            has_end = True
                            print(f"\n   ✅ 结束 (总长度：{len(received_tokens)})")
                        elif event == "error":
                            print(f"   ❌ 错误：{data['data']}")
                            return False
                    except json.JSONDecodeError:
                        continue
        
        full_text = "".join(received_tokens)
        if has_start and has_end and len(full_text) > 0:
            print(f"   ✅ SSE 流式接收成功！内容预览：{full_text[:50]}...")
            return True
        else:
            print("   ❌ 流式数据不完整")
            return False
            
    except Exception as e:
        print(f"   ❌ 异常：{e}")
        return False

def test_get_history(conv_id):
    print(f"\n3️⃣ 测试获取历史记录 - 会话：{conv_id}...")
    resp = requests.get(f"{BASE_URL}/conversations/{conv_id}/messages", headers=HEADERS)
    
    if resp.status_code == 200:
        messages = resp.json()
        print(f"   ✅ 获取成功，共 {len(messages)} 条消息")
        for msg in messages:
            role = msg['role']
            content = msg['content'][:30] + "..." if len(msg['content']) > 30 else msg['content']
            print(f"      - [{role}]: {content}")
        return True
    else:
        print(f"   ❌ 失败：{resp.status_code}")
        return False

def test_preview_prompt():
    print("\n4️⃣ 测试 Prompt 在线预览...")
    payload = {
        "template_content": "你好 {{ user.name }}，当前时间是 {{ current_time }}。",
        "custom_vars": {"topic": "AI"}
    }
    
    resp = requests.post(f"{BASE_URL}/conversations/templates/preview", json=payload, headers=HEADERS)
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            print(f"   ✅ 预览成功：{data['rendered_content']}")
            return True
        else:
            print(f"   ❌ 业务逻辑错误")
            return False
    else:
        print(f"   ❌ 请求失败：{resp.status_code} - {resp.text}")
        return False

if __name__ == "__main__":
    print("🚀 开始 Conversation API 集成测试...")
    
    # 1. 创建会话
    conv_id = test_create_conversation()
    
    if conv_id:
        # 2. 发送消息 (SSE)
        if test_send_message_sse(conv_id):
            # 3. 获取历史
            test_get_history(conv_id)
        else:
            print("\n⚠️ 跳过后续测试，因为消息发送失败。")
    else:
        print("\n⚠️ 跳过后续测试，因为会话创建失败。")
    
    # 4. 独立测试：Prompt 预览
    test_preview_prompt()
    
    print("\n🎉 集成测试完成！")