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
TEST_PROJECT_ID = "9dc5f322-2392-49a1-8455-2241afc1c4bb" 

def test_create_conversation():
    print("\n1️⃣ 测试创建会话...")
    
    # [修复] 动态获取一个可用的模板 ID
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine("postgresql://postgres:postgres@localhost:5432/ai_paas")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id FROM prompt_templates LIMIT 1")).fetchone()
            if not result:
                print("   ❌ 数据库中无可用模板，请先创建一个 Prompt Template")
                return None
            template_id = str(result[0])
            print(f"   📝 自动获取模板 ID: {template_id[:8]}...")
    except Exception as e:
        print(f"   ⚠️ 无法连接数据库获取模板，将尝试不绑定模板创建 (可能会失败): {e}")
        template_id = None

    payload = {
        "project_id": TEST_PROJECT_ID,
        "title": "API 测试会话",
        "template_id": template_id,  # [修复] 绑定模板
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
        resp = requests.post(
            f"{BASE_URL}/conversations/{conv_id}/messages", 
            json=payload, 
            headers=HEADERS, 
            stream=True,
            timeout=60 
        )
        
        if resp.status_code != 200:
            print(f"   ❌ 请求失败：{resp.status_code} - {resp.text}")
            return False
            
        print("   📡 接收流式数据中...")
        received_tokens = []
        has_start = False
        has_end = False
        current_event = None
        
        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                
                # [调试] 可选：打印原始行
                # print(f"   [DEBUG]: {decoded}")

                # 1. 解析 event 行
                if decoded.startswith("event:"):
                    current_event = decoded[6:].strip()
                    continue
                
                # 2. 解析 data 行
                if decoded.startswith("data:"):
                    data_str = decoded[5:].strip()
                    if data_str == "[DONE]": break
                    
                    try:
                        data_content = json.loads(data_str)
                        
                        # 3. 根据 current_event 处理数据
                        if current_event == "start":
                            has_start = True
                            # data_content 应该是 {"message_id": "..."}
                            msg_id = data_content.get("message_id", "unknown") if isinstance(data_content, dict) else "unknown"
                            print(f"   ▶️ 开始 (MsgID: {msg_id})")
                            
                        elif current_event == "token":
                            # data_content 应该是字符串 "你好"
                            if isinstance(data_content, str):
                                received_tokens.append(data_content)
                            elif isinstance(data_content, dict) and "data" in data_content:
                                # 兼容旧格式
                                received_tokens.append(str(data_content["data"]))
                                
                        elif current_event == "end":
                            has_end = True
                            print(f"\n   ✅ 结束 (总长度：{len(received_tokens)})")
                            
                        elif current_event == "error":
                            err_msg = data_content.get("error", str(data_content)) if isinstance(data_content, dict) else str(data_content)
                            print(f"   ❌ 错误：{err_msg}")
                            return False
                            
                    except json.JSONDecodeError:
                        continue
        
        full_text = "".join(received_tokens)
        
        if has_start and has_end:
            print(f"   ✅ SSE 流式接收成功！收到 {len(received_tokens)} 个字符块。")
            if full_text:
                print(f"   内容预览：{full_text[:50]}...")
            return True
        elif len(full_text) > 0:
            print(f"   ⚠️ 未检测到完整事件标记，但接收到了内容：{full_text[:30]}...")
            return True
        else:
            print(f"   ❌ 流式数据不完整 (Start: {has_start}, End: {has_end})")
            return False
            
    except requests.exceptions.Timeout:
        print("   ❌ 请求超时：模型思考时间超过 60 秒。")
        return False
    except Exception as e:
        print(f"   ❌ 异常：{e}")
        import traceback
        traceback.print_exc()
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