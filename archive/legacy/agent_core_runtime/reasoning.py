import asyncio
from typing import Dict, Any

class ReasoningEngine:
    """AI PaaS平台推理引擎 - 支持多模型和智能路由"""
    
    def __init__(self, model_interfaces: Dict[str, Any] = None):
        """
        Args:
            model_interfaces: 模型名称到模型接口的映射
        """
        self.models = model_interfaces or {}
        self.default_model = "deepseek"  # 修正：默认使用 deepseek
    
    def _select_model(self, prompt: str, context: Dict = None) -> str:
        """智能选择最适合的模型"""
        # 基于内容类型的规则选择
        prompt_lower = prompt.lower()
        
        if any(keyword in prompt_lower for keyword in ["代码", "编程", "开发", "code"]):
            return "qwen"  # Qwen 在代码生成方面表现不错
        elif any(keyword in prompt_lower for keyword in ["数学", "逻辑", "推理", "math", "reasoning"]):
            return "deepseek"  # DeepSeek 在推理方面表现优秀
        elif any(keyword in prompt_lower for keyword in ["创意", "写作", "文案", "creative", "write"]):
            return "deepseek"  # 修正：使用 deepseek 而不是不存在的 gpt4
        
        # 可以扩展基于上下文、负载均衡等策略
        return self.default_model
    
    async def think(self, prompt: str, context: Dict = None, model: str = None):
        """执行推理任务"""
        # 自动选择模型或使用指定模型
        selected_model = model or self._select_model(prompt, context)
        
        if selected_model not in self.models:
            available_models = list(self.models.keys())
            return f"错误：模型 {selected_model} 不可用。可用模型: {available_models}"
        
        try:
            # 构建更智能的提示词
            enhanced_prompt = self._enhance_prompt(prompt, context)
            
            # 异步调用模型
            response = await asyncio.to_thread(
                self.models[selected_model].call,
                enhanced_prompt
            )
            
            # 记录推理元数据（用于分析和优化）
            self._log_reasoning_metadata(prompt, selected_model, context)
            
            return response
            
        except Exception as e:
            return f"推理出错 ({selected_model}): {e}"
    
    def _enhance_prompt(self, prompt: str, context: Dict = None) -> str:
        """增强提示词，添加上下文信息"""
        base_prompt = prompt  # 简化提示词增强
        
        if context and context.get('history'):
            base_prompt += f"\n\n相关上下文：{context['history']}"
        
        return base_prompt
    
    def _log_reasoning_metadata(self, prompt: str, model: str, context: Dict):
        """记录推理过程的元数据"""
        metadata = {
            "model_used": model,
            "prompt_length": len(prompt),
            "timestamp": asyncio.get_event_loop().time(),
            "context_info": context.get('type', 'general') if context else 'none'
        }
        print(f"🤖 推理元数据: {metadata}")
    
    def get_available_models(self) -> list:
        """获取可用的模型列表"""
        return list(self.models.keys())
    
    def register_model(self, name: str, model_interface):
        """注册新模型"""
        self.models[name] = model_interface
        print(f"✅ 注册模型: {name}")
    
    def set_default_model(self, model_name: str):
        """设置默认模型"""
        if model_name in self.models:
            self.default_model = model_name
            print(f"✅ 设置默认模型为: {model_name}")
        else:
            print(f"❌ 模型 {model_name} 未注册，无法设置为默认")