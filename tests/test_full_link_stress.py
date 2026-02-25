import pytest
import httpx
import asyncio
import json
import os
from datetime import datetime

# 配置项
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000/api/v1")
TIMEOUT_SECONDS = 30
PROJECT_ID = "00000000-0000-0000-0000-000000000001"  # 假设存在的默认项目ID

@pytest.mark.asyncio
async def test_01_create_conversation():
    """测试用例 1: 创建会话"""
    print("\n[TEST 1] 正在创建会话...")
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        payload = {
            "project_id": PROJECT_ID,
            "title": f"Stress Test Session {datetime.now().strftime('%H%M%S')}",
            "template_id": "11111111-1111-1111-1111-111111111111", 
            "agent_id": None
        }
        
        try:
            response = await client.post(f"{BASE_URL}/conversations/", json=payload)
            
            if response.status_code == 404:
                pytest.skip(f"Project ID {PROJECT_ID} not found. 请确保数据库中存在该项目或修改测试代码中的 PROJECT_ID。")
            
            assert response.status_code == 200, f"创建会话失败 [{response.status_code}]: {response.text}"
            data = response.json()
            assert "id" in data, "响应中缺少 'id' 字段"
            print(f"✅ 会话创建成功: {data['id']}")
            return data['id']
        except Exception as e:
            pytest.fail(f"创建会话过程中发生异常: {str(e)}")

@pytest.mark.asyncio
async def test_02_sse_streaming_stability():
    """测试用例 2: SSE 流式传输稳定性"""
    print("\n[TEST 2] 正在测试 SSE 流式传输...")
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        # 1. 创建临时会话
        conv_payload = {"project_id": PROJECT_ID, "title": "Temp SSE Test", "template_id": "11111111-1111-1111-1111-111111111111"}
        conv_resp = await client.post(f"{BASE_URL}/conversations/", json=conv_payload)
        
        if conv_resp.status_code != 200:
            if conv_resp.status_code == 404:
                pytest.skip(f"Project ID {PROJECT_ID} not found.")
            pytest.fail(f"无法创建临时会话: {conv_resp.text}")
        
        conv_id = conv_resp.json()['id']
        print(f"   临时会话 ID: {conv_id}")

        # 2. 发送消息并接收流
        message_payload = {"content": "请用一句话解释量子纠缠，不要超过50个字。", "role": "user"}
        received_tokens = []
        start_time = asyncio.get_event_loop().time()
        first_token_time = None
        
        try:
            async with client.stream(
                "POST", 
                f"{BASE_URL}/conversations/{conv_id}/messages", 
                json=message_payload
            ) as response:
                assert response.status_code == 200, f"SSE 连接建立失败: {response.status_code}"
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            event_data = json.loads(data_str)
                            if isinstance(event_data, str):
                                received_tokens.append(event_data)
                            elif isinstance(event_data, dict):
                                if "content" in event_data:
                                    received_tokens.append(event_data["content"])
                                if "error" in event_data:
                                    pytest.fail(f"流式传输中收到错误事件: {event_data['error']}")
                            
                            if first_token_time is None and len(received_tokens) > 0:
                                first_token_time = asyncio.get_event_loop().time()
                        except json.JSONDecodeError:
                            continue
            
            end_time = asyncio.get_event_loop().time()
            total_content = "".join(received_tokens)
            
            # 断言检查
            assert len(total_content) > 0, "SSE 流未返回任何内容"
            
            ttft = (first_token_time - start_time) if first_token_time else 999
            assert ttft < 15.0, f"首字延迟 (TTFT) 过高: {ttft:.2f}s (阈值 15s)"
            
            total_duration = end_time - start_time
            print(f"✅ SSE 测试通过 | TTFT: {ttft:.2f}s | 总耗时: {total_duration:.2f}s | 字符数: {len(total_content)}")
            print(f"   内容预览: {total_content[:60]}...")

        except httpx.ReadTimeout:
            pytest.fail("SSE 流式读取超时 (超过 30s)，模型可能卡死或网络中断")
        except Exception as e:
            pytest.fail(f"SSE 测试过程中发生未预期异常: {str(e)}")

@pytest.mark.asyncio
async def test_03_history_consistency():
    """测试用例 3: 历史记录一致性"""
    print("\n[TEST 3] 验证历史记录一致性...")
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        # 创建会话
        conv_payload = {"project_id": PROJECT_ID, "title": "History Test", "template_id": "11111111-1111-1111-1111-111111111111"}
        conv_resp = await client.post(f"{BASE_URL}/conversations/", json=conv_payload)
        if conv_resp.status_code != 200:
             if conv_resp.status_code == 404: pytest.skip(f"Project ID {PROJECT_ID} not found.")
             pytest.fail(f"无法创建会话: {conv_resp.text}")
        
        conv_id = conv_resp.json()['id']
        user_msg = f"测试历史记录的专用消息-{datetime.now().timestamp()}"
        
        # 发送消息
        send_resp = await client.post(f"{BASE_URL}/conversations/{conv_id}/messages", json={"content": user_msg, "role": "user"})
        if send_resp.status_code != 200:
            # 允许流式返回 200，如果是其他错误则失败
            if send_resp.status_code != 200:
                 pytest.fail(f"发送消息失败: {send_resp.text}")

        # 等待写入
        await asyncio.sleep(1.5)
        
        # 查询历史
        hist_resp = await client.get(f"{BASE_URL}/conversations/{conv_id}/messages")
        assert hist_resp.status_code == 200, f"查询历史失败: {hist_resp.text}"
        
        messages = hist_resp.json()
        assert isinstance(messages, list), "历史记录应返回一个列表"
        
        user_messages = [m for m in messages if m.get('role') == 'user']
        assert len(user_messages) >= 1, "历史记录中未找到用户消息"
        assert user_messages[-1]['content'] == user_msg, f"最后一条消息内容不匹配。期望: {user_msg}, 实际: {user_messages[-1]['content']}"
        
        print(f"✅ 历史记录验证通过 | 总消息数: {len(messages)} | 用户消息数: {len(user_messages)}")

@pytest.mark.asyncio
async def test_04_error_handling_invalid_input():
    """测试用例 4: 异常输入处理 (鲁棒性)"""
    print("\n[TEST 4] 测试异常输入处理...")
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        # 创建会话
        conv_payload = {"project_id": PROJECT_ID, "title": "Error Test", "template_id": "11111111-1111-1111-1111-111111111111"}
        conv_resp = await client.post(f"{BASE_URL}/conversations/", json=conv_payload)
        if conv_resp.status_code != 200:
            if conv_resp.status_code == 404: pytest.skip(f"Project ID {PROJECT_ID} not found.")
            pytest.fail(f"无法创建会话: {conv_resp.text}")
        
        conv_id = conv_resp.json()['id']

        # 场景 A: 空内容
        resp_empty = await client.post(f"{BASE_URL}/conversations/{conv_id}/messages", json={"content": "", "role": "user"})
        # 只要不报 500 就算通过 (业务上可以返回 400 或 200)
        if resp_empty.status_code == 500:
            pytest.fail(f"服务器对空内容输入返回了 500 错误: {resp_empty.text}")
        
        # 场景 B: 超长内容 (5000 字符)
        long_text = "A" * 5000
        resp_long = await client.post(f"{BASE_URL}/conversations/{conv_id}/messages", json={"content": long_text, "role": "user"})
        if resp_long.status_code == 500:
            pytest.fail(f"服务器对超长输入返回了 500 错误")

        print("✅ 异常输入处理测试通过 (未发生服务器崩溃 500)")

if __name__ == "__main__":
    print("💡 提示：请使用 'pytest tests/test_full_link_stress.py -v -s' 运行")
