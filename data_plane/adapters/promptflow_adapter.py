# D:\RD\ai-os\data_plane\adapters\promptflow_adapter.py
import aiohttp
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("PromptFlowAdapter")


class PromptFlowAdapter:
    def __init__(self, base_url: str = "http://localhost:8081", timeout_s: int = 30):
        self.base_url = base_url.rstrip("/")
        self.score_url = f"{self.base_url}/score"
        self.timeout_s = timeout_s
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def execute(self, execution_envelope: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 ExecutionEnvelope 转为 PromptFlow 标准化输入并调用 /score
        """
        ctx = execution_envelope.get("context", {}) or {}
        policy = execution_envelope.get("policy", {}) or {}
        inp = execution_envelope.get("input", {}) or {}

        pf_inputs = {
            "user_message": inp.get("user_message") or inp.get("content") or "",
            "user_profile": ctx.get("subject", {}) or {},
            "agent_profile": policy.get("capabilities", {}) or {},
            "memory_hot": inp.get("memory_hot", []),
            "memory_cold": inp.get("memory_cold", []),
            "retrieved_docs": inp.get("retrieved_docs", []),
        }

        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=self.timeout_s)

        async with session.post(self.score_url, json=pf_inputs, timeout=timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"PromptFlow error {resp.status}: {text}")
            return await resp.json()
