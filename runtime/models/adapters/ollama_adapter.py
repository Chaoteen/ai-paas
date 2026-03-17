from __future__ import annotations

from typing import Any, Dict, List

import requests

from runtime.models.exceptions import (
    ModelCapabilityError,
    ModelConfigurationError,
    ModelProviderError,
    ModelTimeoutError,
)
from runtime.models.llm_adapter import LLMAdapter
from runtime.models.types import (
    ChatMessage,
    HealthStatus,
    MessageRole,
    ModelCapability,
    ModelConfig,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolSpec,
    UsageInfo,
)


class OllamaAdapter(LLMAdapter):
    """
    Ollama chat adapter.

    Default expectation:
    endpoint -> Ollama OpenAI-compatible chat endpoint,
    e.g. http://127.0.0.1:11434/v1/chat/completions

    This adapter intentionally uses the OpenAI-compatible Ollama endpoint
    so the platform can unify contracts across local/cloud providers.
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        if not self.config.endpoint:
            raise ModelConfigurationError("endpoint is required for ollama adapter")

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)

        if request.tools and ModelCapability.TOOLS not in self.config.capabilities:
            raise ModelCapabilityError(
                f"ollama model '{self.config.model_name}' does not support tools"
            )

        payload = self._build_payload(request)

        headers = {
            "Content-Type": "application/json",
            **dict(self.config.default_headers),
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            response = requests.post(
                self.config.endpoint,
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ModelTimeoutError("ollama request timed out") from exc
        except requests.RequestException as exc:
            raise ModelProviderError(f"ollama request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ModelProviderError(
                f"ollama returned status={response.status_code} body={response.text}"
            )

        body = response.json()
        return self._parse_response(body=body)

    def health_check(self) -> HealthStatus:
        return HealthStatus(
            ok=True,
            provider=self.config.provider,
            model_name=self.config.model_name,
            detail="health check not actively probing upstream; adapter initialized",
        )

    def _build_payload(self, request: ModelRequest) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "messages": [self._serialize_message(msg) for msg in request.messages],
            **dict(self.config.default_params),
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stream:
            payload["stream"] = True
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in request.tools]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        payload.update(request.extra_params)
        return payload

    def _serialize_message(self, message: ChatMessage) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "role": message.role.value,
            "content": message.content,
        }
        if message.name:
            data["name"] = message.name
        if message.tool_call_id:
            data["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments_json,
                    },
                }
                for tool_call in message.tool_calls
            ]
        return data

    def _serialize_tool(self, tool: ToolSpec) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    def _parse_response(self, body: Dict[str, Any]) -> ModelResponse:
        choices: List[Dict[str, Any]] = body.get("choices") or []
        if not choices:
            raise ModelProviderError("ollama returned no choices")

        first = choices[0]
        message_obj = first.get("message") or {}
        role_str = message_obj.get("role", MessageRole.ASSISTANT.value)
        content = message_obj.get("content") or ""

        tool_calls: List[ToolCall] = []
        for item in message_obj.get("tool_calls") or []:
            function_data = item.get("function") or {}
            tool_calls.append(
                ToolCall(
                    id=item.get("id", ""),
                    name=function_data.get("name", ""),
                    arguments_json=function_data.get("arguments", "{}"),
                )
            )

        usage_obj = body.get("usage") or {}
        usage = UsageInfo(
            prompt_tokens=int(usage_obj.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_obj.get("completion_tokens", 0) or 0),
            total_tokens=int(usage_obj.get("total_tokens", 0) or 0),
        )

        try:
            role = MessageRole(role_str)
        except ValueError:
            role = MessageRole.ASSISTANT

        message = ChatMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            metadata={"provider_raw_message": message_obj},
        )

        return ModelResponse(
            provider=self.config.provider,
            model_name=body.get("model", self.config.model_name),
            message=message,
            finish_reason=first.get("finish_reason"),
            usage=usage,
            raw_response=body,
            latency_ms=None,
        )