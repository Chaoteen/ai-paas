from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from runtime.models.exceptions import (
    ModelAuthenticationError,
    ModelConfigurationError,
    ModelProviderError,
    ModelTimeoutError,
)
from runtime.models.llm_adapter import LLMAdapter
from runtime.models.types import (
    ChatMessage,
    HealthStatus,
    MessageRole,
    ModelConfig,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolSpec,
    UsageInfo,
)


class OpenAICompatibleAdapter(LLMAdapter):
    """
    Generic OpenAI-compatible chat adapter.

    Works for:
    - OpenAI
    - DeepSeek (OpenAI-compatible endpoint)
    - Qwen compatible gateways
    - other OpenAI-style providers
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        if not self.config.endpoint:
            raise ModelConfigurationError(
                f"endpoint is required for provider '{self.config.provider.value}'"
            )

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.validate_request(request)

        start = time.perf_counter()
        payload = self._build_payload(request)

        headers = {
            "Content-Type": "application/json",
            **dict(self.config.default_headers),
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if self.config.organization:
            headers["OpenAI-Organization"] = self.config.organization

        try:
            response = requests.post(
                self.config.endpoint,
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ModelTimeoutError(
                f"request timed out for provider '{self.config.provider.value}'"
            ) from exc
        except requests.RequestException as exc:
            raise ModelProviderError(
                f"http request failed for provider '{self.config.provider.value}': {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise ModelAuthenticationError(
                f"authentication failed for provider '{self.config.provider.value}'"
            )

        if response.status_code >= 400:
            raise ModelProviderError(
                f"provider '{self.config.provider.value}' returned status={response.status_code} "
                f"body={response.text}"
            )

        body = response.json()
        latency_ms = int((time.perf_counter() - start) * 1000)
        return self._parse_response(body=body, latency_ms=latency_ms)

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

    def _parse_response(self, body: Dict[str, Any], latency_ms: int) -> ModelResponse:
        choices: List[Dict[str, Any]] = body.get("choices") or []
        if not choices:
            raise ModelProviderError("provider returned no choices")

        first = choices[0]
        message_obj: Dict[str, Any] = first.get("message") or {}
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
            latency_ms=latency_ms,
            request_id=body.get("id"),
        )


class OpenAIAdapter(OpenAICompatibleAdapter):
    pass