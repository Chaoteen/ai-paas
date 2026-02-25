"""
LLM Service
统一封装 Ollama 和 云端大模型 API，支持流式输出
"""
import os
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI
from config.settings import settings

class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        
        # 根据配置初始化客户端
        if self.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=settings.OLLAMA_BASE_URL,
                api_key="ollama" # Ollama 不需要真实的 key
            )
            self.model_name = settings.OLLAMA_MODEL_NAME
            print(f"🤖 LLM Service 初始化：使用本地 Ollama ({self.model_name})")
            
        else:
            # 默认使用云端 (兼容 OpenAI 格式，如阿里云 DashScope, DeepSeek 官方等)
            if not settings.CLOUD_API_KEY:
                raise ValueError("云端模式需要配置 CLOUD_API_KEY")
                
            self.client = AsyncOpenAI(
                base_url=settings.CLOUD_BASE_URL,
                api_key=settings.CLOUD_API_KEY
            )
            self.model_name = settings.CLOUD_MODEL_NAME
            print(f"☁️ LLM Service 初始化：使用云端模型 ({self.model_name})")

    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天生成器
        :param messages: 消息列表 [{"role": "user", "content": "..."}, ...]
        :yield: 逐个字符或 token 片段
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                stream=True  # 开启流式
            )
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
                        
        except Exception as e:
            error_msg = f"LLM 调用失败：{str(e)}"
            print(f"❌ {error_msg}")
            yield f"\n\n[系统错误]: {error_msg}"

# 单例实例
llm_service = LLMService()