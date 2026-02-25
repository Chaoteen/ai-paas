import httpx
import os
from fastapi import HTTPException, status

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
OPA_POLICY_PATH = os.getenv("OPA_POLICY_PATH", "authz/evaluation_result")

async def check_permission(subject: dict, resource: dict, action: str) -> bool:
    input_data = {
        "input": {
            "subject": subject,
            "resource": resource,
            "action": {"type": action}
        }
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPA_URL}/v1/data/{OPA_POLICY_PATH}",
                json=input_data,
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=503, detail="OPA service unavailable")
            result = response.json()
            allowed = result.get("result", {}).get("allowed", False)
            if not allowed:
                checks = result.get("result", {}).get("checks", {})
                denied = [k for k, v in checks.items() if not v]
                raise HTTPException(status_code=403, detail=f"Permission denied: {', '.join(denied)}")
            return True
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"OPA connection error: {str(e)}")
