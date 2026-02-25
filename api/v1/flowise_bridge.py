from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import httpx
import os

router = APIRouter(prefix="/flowise", tags=["Flowise Integration"])

# 配置项：从环境变量读取，匹配您的启动脚本
# 默认指向本地 8080 端口的 PromptFlow，路径为 /score
PF_BASE_URL = os.getenv("PROMPTFLOW_SERVICE_URL", "http://127.0.0.1:8080")
PROMPTFLOW_ENDPOINT = f"{PF_BASE_URL}/score"

# 简单的 API Key 验证
EXPECTED_API_KEY = os.getenv("FLOWISE_GATEWAY_KEY", "sk-test-flowise-integration-key")

class FlowiseRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = []
    override_config: Optional[Dict[str, Any]] = {}

class FlowiseResponse(BaseModel):
    text: str
    question: str
    history: Optional[List[Dict[str, str]]] = []
    sessionId: Optional[str] = None

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if x_api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key

@router.post("/execute", response_model=FlowiseResponse)
async def execute_prompt(
    request: FlowiseRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Flowise 专用接口：接收用户问题，转发给 PromptFlow，返回结果。
    """
    print(f"[Flowise Bridge] 收到请求: {request.question}")
    print(f"[Flowise Bridge] 目标 PromptFlow 地址: {PROMPTFLOW_ENDPOINT}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 构造 PromptFlow 标准输入 payload
            # 注意：不同的 PromptFlow 流程可能期望不同的输入键名，这里假设标准格式
            pf_payload = {
                "inputs": {
                    "question": request.question,
                    "chat_history": request.history
                }
            }
            
            # 如果 override_config 有内容，合并进去
            if request.override_config:
                pf_payload["inputs"].update(request.override_config)

            resp = await client.post(PROMPTFLOW_ENDPOINT, json=pf_payload)
            
            if resp.status_code == 200:
                result = resp.json()
                # 适配多种可能的返回结构
                # 情况 1: {"output": "answer"}
                # 情况 2: {"result": "answer"}
                # 情况 3: 直接返回字符串 (较少见)
                answer = ""
                if isinstance(result, dict):
                    answer = result.get('output', result.get('result', result.get('answer', str(result))))
                else:
                    answer = str(result)
                    
                return FlowiseResponse(text=answer, question=request.question, history=request.history)
            else:
                error_detail = resp.text[:200]
                print(f"[Flowise Bridge] PromptFlow 返回错误 [{resp.status_code}]: {error_detail}")
                raise HTTPException(status_code=resp.status_code, detail=f"PromptFlow 执行失败: {error_detail}")
                
    except httpx.ConnectError:
        msg = f"无法连接到 PromptFlow 服务 ({PROMPTFLOW_ENDPOINT})。请确保已运行 './run_ai_platform_v2.sh start' 启动 PromptFlow。"
        print(f"[Flowise Bridge] {msg}")
        raise HTTPException(status_code=503, detail=msg)
    except Exception as e:
        print(f"[Flowise Bridge] 发生未预期错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
