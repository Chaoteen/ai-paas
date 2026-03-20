from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SURVIVORS = [
    REPO_ROOT / "data_plane" / "data_bus.py",
    REPO_ROOT / "data_plane" / "redis_stream_bus.py",
    REPO_ROOT / "data_plane" / "event_envelope.py",
    REPO_ROOT / "data_plane" / "data_events.py",
    REPO_ROOT / "data_plane" / "repositories" / "data_event_repository.py",
    REPO_ROOT / "data_plane" / "repositories" / "postgres_data_event_repository.py",
]

def test_data_plane_infrastructure_survivors_exist():
    missing = [str(p.relative_to(REPO_ROOT)) for p in SURVIVORS if not p.exists()]
    assert not missing, "required data_plane infrastructure files missing:\n" + "\n".join(missing)
