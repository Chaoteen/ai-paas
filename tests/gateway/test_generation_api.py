from fastapi.testclient import TestClient

from gateway.main import app
import gateway.api.generation as generation_api


client = TestClient(app)


class FakeGenerationImageService:
    async def generate(self, request, context):
        return {
            "provider": "mock_image",
            "model": "mock-image-v1",
            "output": {
                "task_type": "image",
                "artifacts": [
                    {
                        "uri": "mock://image/generated-1.png",
                        "mime_type": "image/png",
                        "metadata": {
                            "prompt": request.prompt,
                            "width": request.width,
                            "height": request.height,
                        },
                    }
                ],
                "latency_ms": 1,
                "raw_response": {"mock": True},
            },
        }


class FakeGenerationVideoMissingService:
    async def generate(self, request, context):
        raise Exception("no generation model found for provider=seedance capabilities=video")


def test_generation_image_success(monkeypatch):
    def fake_get_generation_service():
        return FakeGenerationImageService()

    monkeypatch.setattr(generation_api, "get_generation_service", fake_get_generation_service)

    response = client.post(
        "/api/v1/generation/image",
        json={
            "prompt": "A futuristic AI-PaaS platform dashboard",
            "provider": "mock_image",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert body["kind"] == "image"
    assert body["provider"] == "mock_image"
    assert body["model"] == "mock-image-v1"
    assert body["output"]["task_type"] == "image"
    assert body["output"]["artifacts"][0]["uri"] == "mock://image/generated-1.png"


def test_generation_video_missing_model_is_normalized(monkeypatch):
    def fake_get_generation_service():
        return FakeGenerationVideoMissingService()

    monkeypatch.setattr(generation_api, "get_generation_service", fake_get_generation_service)

    response = client.post(
        "/api/v1/generation/video",
        json={
            "prompt": "A robot entering a smart factory",
            "duration_seconds": 5,
            "provider": "seedance",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["success"] is False
    assert body["kind"] == "video"
    assert body["provider"] == "seedance"
    assert body["error"]["type"] == "GenerationModelNotFound"
    assert "seedance" in body["error"]["message"].lower()
    assert "AI_PAAS_SEEDANCE_ENDPOINT" in body["error"]["hint"]