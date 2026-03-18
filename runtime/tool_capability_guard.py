from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class ToolCapabilityDecision:
    allowed: bool
    tool_name: str
    required_capabilities: List[str] = field(default_factory=list)
    granted_capabilities: List[str] = field(default_factory=list)
    denied_capabilities: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    @classmethod
    def allow(
        cls,
        *,
        tool_name: str,
        required_capabilities: List[str],
        granted_capabilities: List[str],
    ) -> "ToolCapabilityDecision":
        return cls(
            allowed=True,
            tool_name=tool_name,
            required_capabilities=required_capabilities,
            granted_capabilities=granted_capabilities,
            denied_capabilities=[],
            reasons=[],
        )

    @classmethod
    def deny(
        cls,
        *,
        tool_name: str,
        required_capabilities: List[str],
        granted_capabilities: List[str],
        denied_capabilities: List[str],
        reasons: List[str],
    ) -> "ToolCapabilityDecision":
        return cls(
            allowed=False,
            tool_name=tool_name,
            required_capabilities=required_capabilities,
            granted_capabilities=granted_capabilities,
            denied_capabilities=denied_capabilities,
            reasons=reasons,
        )


class ToolCapabilityGuard:
    """
    Tool-level capability enforcement.

    内置映射规则：
    - echo / template.render: 无敏感 capability
    - http.fetch: network
    - shell.run: shell
    - fs.read: filesystem_read
    - fs.write: filesystem_write
    - secrets.get: secrets
    - generation.image: image_generation
    - generation.video: video_generation
    """

    TOOL_CAPABILITY_MAP: Dict[str, List[str]] = {
        "echo": [],
        "template.render": [],
        "http.fetch": ["network"],
        "shell.run": ["shell"],
        "fs.read": ["filesystem_read"],
        "fs.write": ["filesystem_write"],
        "secrets.get": ["secrets"],
        "generation.image": ["image_generation"],
        "generation.video": ["video_generation"],
    }

    def evaluate(
        self,
        *,
        tool_name: str,
        allowed_capabilities: List[str] | None,
    ) -> ToolCapabilityDecision:
        required = sorted(self.TOOL_CAPABILITY_MAP.get(tool_name, []))
        allowed_set = set(str(x) for x in (allowed_capabilities or []))

        if not required:
            return ToolCapabilityDecision.allow(
                tool_name=tool_name,
                required_capabilities=[],
                granted_capabilities=[],
            )

        granted = sorted([cap for cap in required if cap in allowed_set])
        denied = sorted([cap for cap in required if cap not in allowed_set])

        if denied:
            return ToolCapabilityDecision.deny(
                tool_name=tool_name,
                required_capabilities=required,
                granted_capabilities=granted,
                denied_capabilities=denied,
                reasons=[
                    (
                        f"Tool '{tool_name}' requires capabilities "
                        f"{', '.join(required)} but runtime only grants "
                        f"{', '.join(sorted(allowed_set)) if allowed_set else '(none)'}; "
                        f"denied: {', '.join(denied)}"
                    )
                ],
            )

        return ToolCapabilityDecision.allow(
            tool_name=tool_name,
            required_capabilities=required,
            granted_capabilities=granted,
        )