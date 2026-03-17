from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data_plane.event_envelope import EventEnvelope

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


@dataclass
class ConsumedMessage:
    stream: str
    message_id: str
    envelope: EventEnvelope


class RedisStreamBus:
    def __init__(
        self,
        redis_client: Any,
        *,
        max_stream_length: int = 10000,
        dead_letter_suffix: str = ".dlq",
    ) -> None:
        self.redis = redis_client
        self.max_stream_length = max_stream_length
        self.dead_letter_suffix = dead_letter_suffix

    @classmethod
    def from_env(cls) -> "RedisStreamBus":
        if redis is None:
            raise RuntimeError("redis package is not installed. Please run: pip install redis")

        host = os.getenv("AI_PAAS_REDIS_HOST", "127.0.0.1")
        port = int(os.getenv("AI_PAAS_REDIS_PORT", "6379"))
        db = int(os.getenv("AI_PAAS_REDIS_DB", "0"))
        password = os.getenv("AI_PAAS_REDIS_PASSWORD")

        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
        )
        client.ping()
        return cls(client)

    def publish(self, envelope: EventEnvelope) -> str:
        body = json.dumps(envelope.to_dict(), ensure_ascii=False)
        message_id = self.redis.xadd(
            envelope.stream,
            {"message": body},
            maxlen=self.max_stream_length,
            approximate=True,
        )
        return message_id

    def publish_event(
        self,
        *,
        stream: str,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        schema_version: str = "1.0",
    ) -> EventEnvelope:
        envelope = EventEnvelope.new(
            event_type=event_type,
            stream=stream,
            source=source,
            payload=payload,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            task_id=task_id,
            workflow_id=workflow_id,
            headers=headers,
            schema_version=schema_version,
        )
        self.publish(envelope)
        return envelope

    def ensure_group(self, stream: str, group_name: str, start_id: str = "0") -> None:
        try:
            self.redis.xgroup_create(stream, group_name, id=start_id, mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def consume(
        self,
        *,
        stream: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 1000,
    ) -> List[ConsumedMessage]:
        response = self.redis.xreadgroup(
            group_name,
            consumer_name,
            {stream: ">"},
            count=count,
            block=block_ms,
        )

        results: List[ConsumedMessage] = []
        for stream_name, messages in response:
            for message_id, fields in messages:
                raw = fields.get("message")
                if raw is None:
                    continue
                data = json.loads(raw)
                envelope = EventEnvelope.from_dict(data)
                results.append(
                    ConsumedMessage(
                        stream=stream_name,
                        message_id=message_id,
                        envelope=envelope,
                    )
                )
        return results

    def ack(self, stream: str, group_name: str, message_id: str) -> int:
        return int(self.redis.xack(stream, group_name, message_id))

    def dead_letter(
        self,
        *,
        original_stream: str,
        envelope: EventEnvelope,
        reason: str,
    ) -> str:
        dlq_stream = f"{original_stream}{self.dead_letter_suffix}"
        dlq_payload = {
            "reason": reason,
            "original_stream": original_stream,
            "envelope": envelope.to_dict(),
        }
        dlq_envelope = EventEnvelope.new(
            event_type=f"{envelope.event_type}.dead_letter",
            stream=dlq_stream,
            source="redis_stream_bus",
            payload=dlq_payload,
            tenant_id=envelope.tenant_id,
            correlation_id=envelope.correlation_id,
            task_id=envelope.task_id,
            workflow_id=envelope.workflow_id,
            headers={"dead_letter": True},
        )
        return self.publish(dlq_envelope)

    def healthcheck(self) -> bool:
        try:
            self.redis.ping()
            return True
        except Exception:
            return False