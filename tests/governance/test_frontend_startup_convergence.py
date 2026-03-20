from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "start_frontend.sh"


def test_frontend_startup_script_targets_vite_webapp():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "webapp" in text
    assert "5173" in text
    assert "npm run dev" in text


def test_frontend_startup_script_does_not_claim_flowise_as_formal_frontend():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = [
        "当前前端由 Flowise",
        "Flowise (Docker) 提供",
        "http://localhost:3000",
    ]
    for item in forbidden:
        assert item not in text, f"legacy frontend wording still present: {item}"
