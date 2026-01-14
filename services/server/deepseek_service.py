# server/deepseek_service.py
import os
import logging
import requests
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DeepSeekService:
    """
    DeepSeek 模型服务封装类
    智能降级机制：Ollama → Local → API（如有Key）
    """

    def __init__(self):
        # 配置运行模式：auto, ollama, local, api
        self.mode = os.getenv("DEEPSEEK_MODE", "auto")  # auto | ollama | local | api
        
        # Ollama 配置
        self.ollama_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")
        self.ollama_available = False
        
        # API 配置
        self.api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.api_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.api_available = False
        
        # Local 配置
        self.local_model_name = os.getenv("LOCAL_MODEL", "deepseek-ai/deepseek-llm-7b-chat")
        self.local_available = False

        logger.info(f"🤖 DeepSeek 服务初始化，模式: {self.mode.upper()}")

        # 自动检测可用服务
        if self.mode == "auto":
            self._auto_detect_services()
        else:
            self._setup_specific_mode()

    def _auto_detect_services(self):
        """自动检测可用的服务，按优先级排序"""
        logger.info("🔄 自动检测可用AI服务...")
        
        # 1. 优先检测 Ollama
        self.ollama_available = self._check_ollama_connection()
        if self.ollama_available:
            self.mode = "ollama"
            logger.info("🎯 自动选择: Ollama 模式")
            return
        
        # 2. 检测本地模型
        self.local_available = self._setup_local_model(silent=True)
        if self.local_available:
            self.mode = "local"
            logger.info("🎯 自动选择: Local 模式")
            return
        
        # 3. 最后检测 API（需要Key）
        self.api_available = self._check_api_availability()
        if self.api_available:
            self.mode = "api"
            logger.info("🎯 自动选择: API 模式")
            return
        
        # 4. 所有模式都不可用
        logger.error("❌ 所有AI服务都不可用！")
        self.mode = "none"

    def _setup_specific_mode(self):
        """设置特定模式"""
        if self.mode == "ollama":
            self.ollama_available = self._check_ollama_connection()
            if not self.ollama_available:
                logger.error("❌ Ollama 模式配置但服务不可用")
                
        elif self.mode == "local":
            self.local_available = self._setup_local_model()
            if not self.local_available:
                logger.error("❌ Local 模式配置但模型加载失败")
                
        elif self.mode == "api":
            self.api_available = self._check_api_availability()
            if not self.api_available:
                logger.error("❌ API 模式配置但API不可用")

    def _check_ollama_connection(self):
        """检查Ollama服务连接"""
        try:
            response = requests.get(f"{self.ollama_base}/api/tags", timeout=5)
            if response.status_code == 200:
                models = [m['name'] for m in response.json().get('models', [])]
                logger.info(f"✅ Ollama 服务可用! 模型: {models}")
                return True
            else:
                logger.warning(f"⚠️ Ollama 服务响应异常: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Ollama 服务不可用: {e}")
            return False

    def _setup_local_model(self, silent=False):
        """设置本地模型"""
        if not silent:
            logger.info("🧠 正在加载本地 DeepSeek 模型...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.local_model_name, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.local_model_name,
                device_map="auto",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                trust_remote_code=True
            ).eval()
            if not silent:
                logger.info("✅ 本地 DeepSeek 模型加载成功")
            return True
        except Exception as e:
            if not silent:
                logger.error(f"❌ 本地模型加载失败: {e}")
            return False

    def _check_api_availability(self):
        """检查API是否可用（需要有效的API Key）"""
        if not self.api_key:
            logger.warning("⚠️ API 模式需要 DEEPSEEK_API_KEY 环境变量")
            return False
        
        try:
            # 简单的API可用性检查
            url = f"{self.api_base}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.info("✅ DeepSeek API 可用")
                return True
            else:
                logger.warning(f"⚠️ DeepSeek API 不可用: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"⚠️ DeepSeek API 检查失败: {e}")
            return False

    def generate_text(self, prompt: str):
        """生成文本，带自动降级机制"""
        if not prompt or not isinstance(prompt, str):
            return {"success": False, "error": "Prompt 不能为空"}

        # 根据模式调用相应方法
        if self.mode == "ollama" and self.ollama_available:
            return self._generate_via_ollama(prompt)
        elif self.mode == "local" and self.local_available:
            return self._generate_via_local(prompt)
        elif self.mode == "api" and self.api_available:
            return self._generate_via_api(prompt)
        else:
            # 降级到模拟响应
            return self._generate_via_fallback(prompt)

    def _generate_via_ollama(self, prompt: str):
        """通过本地Ollama服务生成文本"""
        url = f"{self.ollama_base}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 1000
            }
        }

        try:
            logger.info(f"📨 调用本地 Ollama: {prompt[:50]}...")
            response = requests.post(url, json=payload, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("response", "").strip()
                logger.info(f"✅ Ollama 响应成功，生成 {data.get('eval_count', 0)} tokens")
                return {
                    "success": True, 
                    "content": content,
                    "thinking": data.get("thinking", ""),
                    "metrics": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0)
                    }
                }
            else:
                error_msg = f"Ollama API 错误: {response.status_code}"
                logger.error(f"❌ {error_msg}")
                # 如果Ollama失败，标记为不可用并尝试降级
                self.ollama_available = False
                return self.generate_text(prompt)  # 递归调用，触发降级
                
        except Exception as e:
            error_msg = f"Ollama 调用失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.ollama_available = False
            return self.generate_text(prompt)  # 递归调用，触发降级

    def _generate_via_local(self, prompt: str):
        """通过本地模型生成文本"""
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )
            content = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return {"success": True, "content": content}
        except Exception as e:
            logger.error(f"❌ 本地推理失败: {e}")
            self.local_available = False
            return self.generate_text(prompt)  # 降级

    def _generate_via_api(self, prompt: str):
        """通过DeepSeek官方API生成文本"""
        # 只有在有API Key时才调用
        if not self.api_key:
            logger.error("❌ API 模式需要有效的 API Key")
            self.api_available = False
            return self.generate_text(prompt)  # 降级

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.api_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return {"success": True, "content": content}
        except Exception as e:
            logger.error(f"❌ DeepSeek API 调用失败: {e}")
            self.api_available = False
            return self.generate_text(prompt)  # 降级

    def _generate_via_fallback(self, prompt: str):
        """降级方案：返回模拟响应"""
        logger.warning("⚠️ 所有AI服务都不可用，使用模拟响应")
        return {
            "success": True,
            "content": f"模拟响应: {prompt} (AI服务暂不可用，请检查Ollama服务)",
            "fallback": True
        }

# 全局服务实例
deepseek_service = DeepSeekService()