from __future__ import annotations

import pytest

from bootstrap.outbox_relay_runner import (
    _float_env,
    _get_redis_url,
    _positive_int_env,
    build_outbox_relay,
)


def test_positive_int_env_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("OUTBOX_RETRY_BACKOFF_SECONDS", raising=False)
    assert _positive_int_env("OUTBOX_RETRY_BACKOFF_SECONDS", 5) == 5


def test_positive_int_env_rejects_zero(monkeypatch):
    monkeypatch.setenv("OUTBOX_MAX_PUBLISH_ATTEMPTS", "0")
    with pytest.raises(ValueError, match="OUTBOX_MAX_PUBLISH_ATTEMPTS must be > 0"):
        _positive_int_env("OUTBOX_MAX_PUBLISH_ATTEMPTS", 10)


def test_float_env_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("OUTBOX_RELAY_SLEEP_SECONDS", "0")
    with pytest.raises(ValueError, match="OUTBOX_RELAY_SLEEP_SECONDS must be > 0"):
        _float_env("OUTBOX_RELAY_SLEEP_SECONDS", 1.0)


def test_get_redis_url_requires_env(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(ValueError, match="REDIS_URL is required"):
        _get_redis_url()


@pytest.mark.asyncio
async def test_build_outbox_relay_reads_config_from_runner(monkeypatch):
    class DummyQueueClient:
        def __init__(self, redis_url: str):
            self.redis_url = redis_url

    async def fake_session_factory():
        async def _factory():
            raise AssertionError("session factory should not be entered in this test")
        return _factory

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379")
    monkeypatch.setenv("OUTBOX_RETRY_BACKOFF_SECONDS", "7")
    monkeypatch.setenv("OUTBOX_MAX_PUBLISH_ATTEMPTS", "11")

    monkeypatch.setattr(
        "bootstrap.outbox_relay_runner.get_postgres_session_factory",
        fake_session_factory,
    )
    monkeypatch.setattr(
        "bootstrap.outbox_relay_runner.RedisStreamQueueClient",
        DummyQueueClient,
    )

    relay = await build_outbox_relay()

    assert relay.retry_backoff_seconds == 7
    assert relay.max_publish_attempts == 11
    assert relay.queue_client.redis_url == "redis://127.0.0.1:6379"