import httpx
from .config import settings


class OPAClient:
    def __init__(self, base_url: str = settings.OPA_URL):
        self.base_url = base_url.rstrip("/")

    async def query_allow(self, input_doc: dict) -> bool:
        """
        Call OPA data endpoint: POST /v1/data/ui/allow  { "input": {...} }
        OPA should return: { "result": true/false }  (or nested)
        """
        url = self.base_url + settings.OPA_UI_POLICY_PATH
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(url, json={"input": input_doc})
            r.raise_for_status()
            data = r.json()
            # Most common: {"result": true}
            result = data.get("result")
            if isinstance(result, bool):
                return result
            # fallback: {"result": {"allow": true}}
            if isinstance(result, dict) and isinstance(result.get("allow"), bool):
                return bool(result["allow"])
            return False
